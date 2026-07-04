"""Catalogo de clips de fundo do Google Drive (rclone), multi-tag, com cache local sob demanda.

Acesso: rclone remote gdrive (OAuth da conta do usuario). Pastas compartilhadas via link sao
acessadas pelo folder-ID com --drive-root-folder-id (o path por ID falha com "directory not
found"). A listagem e recursiva para pegar .mp4 em subpastas. O download e sob demanda:
pick_drive_clip escolhe um clip no indice e so baixa se ainda nao estiver em cache.
"""

import logging
import random
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# tag de template -> folder IDs do Drive (pastas compartilhadas via link).
# IDs validados em 28/06/2026 via `rclone lsf gdrive: --drive-root-folder-id={ID} --recursive`.
# Pastas mortas ("Link Trocado!") do gdoc jetflix foram excluidas; ficam as compartilhadas confiaveis.
FOLDER_TAG_MAP: dict[str, list[str]] = {
    "satisfying": [
        "1lkZLuMaXrepi3bMtwk3QxWmYCBlStCiV",  # VIDEOS VIRAIS PACK 1 (~2392)
        "1uQ5Q67XkZ2WEEfhYylcNM1RNnr62Ezye",  # VIDEOS VIRAIS PACK 3
        "1Ig4lH76-_kGmESisS7AiCz4aXUpoqnFO",  # 40 Videos Virais
    ],
    "lifestyle": [
        "11HxCRAAyNUmH7tb9EuQllBu3DW-HrLo9",  # Pack 1000 lifestyle (~1051)
        "1YdNOjmAwmjT2ZXO8UjLpRQexKGFu5Zbe",  # Homens de poder (~43)
    ],
    "cinematic": [
        "1BxIvXI5bEp5u_t6Dff17YAkqI_Qzl7kq",  # cortes filmes e series (~256)
        "1p8ITT6kZtKzjh3TtNNZwU6kxgwCYU4yB",  # Pack Filmes e Series
    ],
    "nature": [
        "14-Qb0gplGCrIoUf_mLRIm6Ms02NUVsdf",  # Animais e Natureza (~31)
    ],
    "fitness": [
        "13yqde3v5mZi4fK0TCM29h5tjEykSQtMM",  # Academia (~67)
        "1CTA879c5NfUZ2co_YT0b-OYj3WbxqGf_",
    ],
    "humor": [
        "17-lkb-3wZhcmjRYMyxyvVUuPmy-JZM24",  # Memes (~48)
        "1qNk9z3tX5HTVzBH1HzROp7T5oYAi8Vdd",  # Engracados
    ],
    "fails": [
        "1G7hG-kKKzy0epPXhvBB74kboZvkUJB66",  # Quedas (~114)
    ],
    "impactantes": [
        "1TITYQcTyELc7hYEdq6kxMXQ-v09fZ3ty",  # (~37)
    ],
    "podcast": [
        "1w39mnEVowJrBY-paQYcPJydeqCQ5VTkm",  # Cortes Marcal
        "1Guth9XhmcJbid-5POCdEeLMWCXAyElyj",  # Cortes Marcal
    ],
    "stock": [
        "1BRYiVzoDk9THjnRvX8ZU6CHhqbhTco0D",  # STOCK VIDEOS (b-roll generico)
    ],
}

_DB_PATH = settings.STORAGE_DIR / "drive_index.db"
_CACHE_DIR = settings.STORAGE_DIR / "library" / "cache"
_RCLONE_DEFAULT_TIMEOUT_SECONDS = 300
_RCLONE_BATCH_TIMEOUT_SECONDS = 1800
_RCLONE_BATCH_SIZE = 100
_RCLONE_BATCH_TPS_LIMIT = "2"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS drive_clips (
            remote_path TEXT PRIMARY KEY,   -- "{folder_id}/{name}"
            tag TEXT NOT NULL,
            folder_id TEXT NOT NULL,
            name TEXT NOT NULL,
            cached_path TEXT,
            indexed_at TEXT
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drive_clips_tag ON drive_clips(tag)")
    # Migracao: embedding CLIP (vetor 512-dim float32 normalizado) para busca semantica.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(drive_clips)").fetchall()}
    if "embedding" not in cols:
        conn.execute("ALTER TABLE drive_clips ADD COLUMN embedding BLOB")
    return conn


def _rclone(*args: str, timeout: int = _RCLONE_DEFAULT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    cmd = [settings.RCLONE_EXE, *args]
    # encoding=utf-8: nomes de arquivo do Drive tem acentos/emoji; cp1252 (default Win) quebra.
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        stderr = f"rclone timed out after {timeout}s: {e}"
        logger.warning(stderr)
        return subprocess.CompletedProcess(cmd, returncode=124, stdout=e.stdout or "", stderr=stderr)


def list_remote_clips(folder_id: str) -> list[str]:
    """Nomes de .mp4 numa pasta do Drive (recursivo — pega subpastas)."""
    res = _rclone(
        "lsf",
        f"{settings.RCLONE_REMOTE}:",
        "--drive-root-folder-id",
        folder_id,
        "--recursive",
        "--files-only",
    )
    if res.returncode != 0:
        logger.warning("rclone lsf falhou p/ '%s': %s", folder_id, res.stderr[:200])
        return []
    return [ln.strip() for ln in res.stdout.splitlines() if ln.strip().lower().endswith(".mp4")]


def index_folder(folder_id: str, tag: str) -> int:
    """Indexa (upsert) os .mp4 de uma pasta sob uma tag. Retorna quantos indexou."""
    names = list_remote_clips(folder_id)
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        for name in names:
            remote_path = f"{folder_id}/{name}"
            conn.execute(
                """INSERT INTO drive_clips (remote_path, tag, folder_id, name, indexed_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(remote_path)
                   DO UPDATE SET tag=excluded.tag, indexed_at=excluded.indexed_at""",
                (remote_path, tag, folder_id, name, now),
            )
        conn.commit()
    return len(names)


def index_all() -> dict[str, int]:
    """Indexa todas as pastas do FOLDER_TAG_MAP. Retorna {tag: total_indexado}."""
    totals: dict[str, int] = {}
    for tag, folder_ids in FOLDER_TAG_MAP.items():
        for fid in folder_ids:
            n = index_folder(fid, tag)
            totals[tag] = totals.get(tag, 0) + n
            logger.info("[drive] %s <- %s: +%d clips", tag, fid, n)
    return totals


def count_for_tag(tag: str) -> int:
    with _conn() as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM drive_clips WHERE tag=?", (tag,)).fetchone()
    return int(n)


def _ensure_cached(remote_path: str, tag: str, name: str, cached_path: str | None) -> Path | None:
    """Baixa o clip do Drive para o cache local se ainda nao estiver. Retorna o Path local."""
    if cached_path and Path(cached_path).exists():
        return Path(cached_path)
    folder_id, _, fname = remote_path.partition("/")
    dest_dir = _CACHE_DIR / tag
    dest_dir.mkdir(parents=True, exist_ok=True)
    res = _rclone(
        "copy",
        f"{settings.RCLONE_REMOTE}:",
        "--drive-root-folder-id",
        folder_id,
        "--include",
        fname,
        str(dest_dir),
    )
    local = dest_dir / name
    if res.returncode != 0 or not local.exists():
        logger.warning("rclone copy falhou p/ '%s': %s", remote_path, getattr(res, "stderr", "")[:200])
        return None
    with _conn() as conn:
        conn.execute("UPDATE drive_clips SET cached_path=? WHERE remote_path=?", (str(local), remote_path))
        conn.commit()
    return local


def pick_drive_clip(tag: str) -> Path | None:
    """Escolhe um clip aleatorio da tag no indice e garante o cache local."""
    with _conn() as conn:
        rows = conn.execute("SELECT remote_path, name, cached_path FROM drive_clips WHERE tag=?", (tag,)).fetchall()
    if not rows:
        return None
    remote_path, name, cached_path = random.choice(rows)
    return _ensure_cached(remote_path, tag, name, cached_path)


# --- Camada semantica (CLIP) — busca por significado dentro de uma tag -------------
# Imports pesados (torch/sentence-transformers/PIL/numpy) sao lazy: o modulo importa sem
# a dep, e search_clips/index_embeddings sao no-ops/sempre-fallback se faltar. Dep:
# `pip install torch sentence-transformers` (CUDA para GPU; ver clip_rerank.py).

_clip_model = None


def _get_clip_model():
    """CLIP ViT-B/32 (espaco multimodal: texto e imagem no mesmo espaco). Cache global."""
    global _clip_model
    if _clip_model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _clip_model = SentenceTransformer("clip-ViT-B-32", device=device)
        logger.info("CLIP clip-ViT-B-32 carregado em %s", device)
    return _clip_model


def _extract_frame(video_path: Path):
    """Frame do meio do clip via ffmpeg/ffprobe. Retorna PIL.Image RGB ou None."""
    import json
    from io import BytesIO

    from PIL import Image

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        dur = float(json.loads(probe.stdout)["format"]["duration"])
    except (ValueError, KeyError):
        dur = 2.0
    ts = max(0.0, dur / 2)
    out = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "quiet",
            "-ss",
            str(ts),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ],
        capture_output=True,
    )
    if not out.stdout:
        return None
    try:
        return Image.open(BytesIO(out.stdout)).convert("RGB")
    except Exception as e:  # noqa: BLE001 — clip corrompido so nao embedda
        logger.warning("frame falhou p/ %s: %s", video_path.name, e)
        return None


def _download_batch(folder_id: str, names: list[str], dest_dir: Path) -> None:
    """Baixa varios arquivos de uma pasta em UMA chamada rclone (--files-from).
    1 listagem da pasta — evita o custo de listar a cada --include (PACK1 tem 2392 itens)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    import tempfile

    for start in range(0, len(names), _RCLONE_BATCH_SIZE):
        batch = names[start : start + _RCLONE_BATCH_SIZE]
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8", newline="") as f:
            for n in batch:
                f.write(n + "\n")
            files_from = f.name
        try:
            res = _rclone(
                "copy",
                f"{settings.RCLONE_REMOTE}:",
                "--drive-root-folder-id",
                folder_id,
                "--files-from",
                files_from,
                "--tpslimit",
                _RCLONE_BATCH_TPS_LIMIT,
                "--retries",
                "5",
                "--low-level-retries",
                "20",
                str(dest_dir),
                timeout=_RCLONE_BATCH_TIMEOUT_SECONDS,
            )
            if res.returncode != 0:
                logger.warning(
                    "rclone batch copy falhou p/ pasta %s (%d-%d/%d): %s",
                    folder_id,
                    start + 1,
                    start + len(batch),
                    len(names),
                    res.stderr[:300],
                )
            else:
                downloaded = sum(1 for name in batch if (dest_dir / name).exists())
                if downloaded == 0 and batch:
                    logger.warning(
                        "rclone batch copy baixou 0 arquivos p/ pasta %s (%d-%d/%d)",
                        folder_id,
                        start + 1,
                        start + len(batch),
                        len(names),
                    )
        finally:
            Path(files_from).unlink(missing_ok=True)


def index_embeddings(tag: str, limit: int | None = None) -> int:
    """Embedda (CLIP) clips da tag sem embedding. Baixa em batch por pasta (--files-from:
    1 listagem por pasta, evita rate-limit do Drive) e embedda os frames na GPU.
    Retorna quantos embeddou. Batch one-time (rodar via scripts/index_library.py)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT remote_path, folder_id, name, cached_path FROM drive_clips " "WHERE tag=? AND embedding IS NULL",
            (tag,),
        ).fetchall()
    if limit:
        rows = rows[:limit]
    if not rows:
        return 0
    import numpy as np

    # 1. Baixar em batch por pasta os clips ainda nao cached (1 listagem por pasta)
    cache_dir = _CACHE_DIR / tag
    by_folder: dict[str, list[tuple[str, str]]] = {}
    for remote_path, folder_id, name, cached_path in rows:
        if cached_path and Path(cached_path).exists():
            continue
        by_folder.setdefault(folder_id, []).append((remote_path, name))
    for folder_id, items in by_folder.items():
        _download_batch(folder_id, [nm for _, nm in items], cache_dir)
        with _conn() as conn:
            for remote_path, name in items:
                local = cache_dir / name
                if local.exists():
                    conn.execute(
                        "UPDATE drive_clips SET cached_path=? WHERE remote_path=?",
                        (str(local), remote_path),
                    )
            conn.commit()

    # 2. Embeddar os frames (CLIP na GPU)
    model = _get_clip_model()
    n = 0
    for remote_path, folder_id, name, cached_path in rows:
        local = cache_dir / name
        if not local.exists():
            continue
        frame = _extract_frame(local)
        if frame is None:
            continue
        vec = model.encode([frame], convert_to_numpy=True, normalize_embeddings=True)[0]
        blob = vec.astype(np.float32).tobytes()
        with _conn() as conn:
            conn.execute("UPDATE drive_clips SET embedding=? WHERE remote_path=?", (blob, remote_path))
            conn.commit()
        n += 1
        if n % 50 == 0:
            logger.info("[embed] %s: %d embeddados", tag, n)
    logger.info("[embed] %s: concluido, %d embeddados", tag, n)
    return n


def search_clips(query: str, tag: str, k: int = 1, exclude: set[str] | None = None) -> list[Path]:
    """Top-k clips da tag por similaridade semantica (CLIP) ao texto da query.
    Fallback aleatorio se nao houver embeddings indexadas (ou dep ausente)."""
    exclude = exclude or set()
    try:
        import numpy as np

        with _conn() as conn:
            rows = conn.execute(
                "SELECT remote_path, name, cached_path, embedding FROM drive_clips "
                "WHERE tag=? AND embedding IS NOT NULL",
                (tag,),
            ).fetchall()
        if not rows:
            raise RuntimeError("sem embeddings para a tag")

        model = _get_clip_model()
        q = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
        scored = []
        for remote_path, name, cached_path, blob in rows:
            if name in exclude:
                continue
            vec = np.frombuffer(blob, dtype=np.float32)
            scored.append((float(vec @ q), remote_path, name, cached_path))  # cosine (norm.)
        scored.sort(reverse=True)
        paths: list[Path] = []
        for _, remote_path, name, cached_path in scored[:k]:
            p = _ensure_cached(remote_path, tag, name, cached_path)
            if p:
                paths.append(p)
        return paths
    except Exception as e:  # noqa: BLE001 — sem dep/embeddings: fallback aleatorio
        logger.warning("search_clips fallback p/ '%s' (%s): %s", tag, query[:40], e)
        # fallback: k clips aleatorios da tag, evitando exclude
        with _conn() as conn:
            rows = conn.execute("SELECT remote_path, name, cached_path FROM drive_clips WHERE tag=?", (tag,)).fetchall()
        pool = [r for r in rows if r[1] not in exclude] or rows
        if not pool:
            return []
        picks = random.sample(pool, min(k, len(pool)))
        return [p for p in (_ensure_cached(rp, tag, nm, cp) for rp, nm, cp in picks) if p]
