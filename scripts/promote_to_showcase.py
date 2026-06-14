"""Promove um job concluido para o showcase: copia o mp4 e injeta a entry no manifesto.

Substitui o passo manual "copiar arquivo + editar showcase.json na mao". Por padrao o video
vai para storage/showcase/<slug>.mp4 (galeria servida pelo backend via /storage/showcase);
com --hero vai para frontend/public/showcase/<slug>.mp4 (commitado, carrega sempre na home).

Uso (stack nao precisa estar rodando — so le o arquivo final ja gerado):
    python -m scripts.promote_to_showcase <job_id> <niche> "<titulo>" \
        [--phrase "gancho"] [--before-script "primeira linha do roteiro"] \
        [--hero] [--caption-style tiktok|impact|karaoke|minimal|boxed] [--template-label "..."]
"""

import argparse
import json
import re
import shutil
import unicodedata
from pathlib import Path

# Estilo por nicho (espelha frontend/src/lib/niches.ts — accent/gradient/icon coerentes).
NICHE_STYLE: dict[str, dict[str, str]] = {
    "curiosidades": {
        "accent": "#22d3ee",
        "gradient": "from-blue-900/60 to-cyan-900/60",
        "icon": "🧠",
        "template": "Narração + Stock",
    },
    "religioso": {
        "accent": "#fbbf24",
        "gradient": "from-amber-900/60 to-yellow-900/50",
        "icon": "🙏",
        "template": "Narração + Stock",
    },
    "motivacional": {
        "accent": "#fb923c",
        "gradient": "from-orange-900/60 to-red-900/50",
        "icon": "🔥",
        "template": "Narração + Stock",
    },
    "financas": {
        "accent": "#34d399",
        "gradient": "from-emerald-900/60 to-green-900/50",
        "icon": "💰",
        "template": "Narração + Stock",
    },
    "historias": {
        "accent": "#c084fc",
        "gradient": "from-purple-900/60 to-indigo-900/60",
        "icon": "📖",
        "template": "Story Time",
    },
    "humor": {
        "accent": "#f472b6",
        "gradient": "from-pink-900/60 to-fuchsia-900/50",
        "icon": "😂",
        "template": "Personagem Narrador",
    },
    "drama": {
        "accent": "#f87171",
        "gradient": "from-red-900/60 to-rose-950/60",
        "icon": "🎭",
        "template": "Drama Histórico",
    },
}
_DEFAULT_STYLE = {
    "accent": "#22d3ee",
    "gradient": "from-blue-900/60 to-cyan-900/60",
    "icon": "🎬",
    "template": "Narração + Stock",
}


def slugify(text: str) -> str:
    """Slug ASCII, minusculo, hifenizado, max 50 chars. Fallback 'video' se vazio."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:50] or "video"


def promote_video(
    job_id: str,
    niche: str,
    title: str,
    *,
    output_dir: Path,
    showcase_storage_dir: Path,
    public_showcase_dir: Path,
    manifest_path: Path,
    hero: bool = False,
    phrase: str = "",
    before_script: str = "",
    caption_style: str = "tiktok",
    template_label: str | None = None,
) -> dict:
    """Copia storage/output/<job_id>.mp4 para o destino e insere a entry no topo do manifesto.

    Idempotente por slug do titulo (re-promover o mesmo titulo substitui a entry).
    """
    source = output_dir / f"{job_id}.mp4"
    if not source.exists():
        raise FileNotFoundError(f"Video final nao encontrado: {source}")

    slug = slugify(title)
    style = NICHE_STYLE.get(niche, _DEFAULT_STYLE)

    if hero:
        dest = public_showcase_dir / f"{slug}.mp4"
        video_url = f"/showcase/{slug}.mp4"
    else:
        dest = showcase_storage_dir / f"{slug}.mp4"
        video_url = f"/storage/showcase/{slug}.mp4"

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)

    entry: dict = {
        "id": slug,
        "title": title,
        "template": template_label or style["template"],
        "niche": niche,
        "video": video_url,
        "phrase": phrase or title,
        "captionStyle": caption_style,
        "captionAccent": style["accent"],
        "gradient": style["gradient"],
        "icon": style["icon"],
    }
    if hero:
        entry["hero"] = True
    if before_script:
        entry["beforeScript"] = before_script

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["videos"] = [v for v in manifest["videos"] if v.get("id") != slug]
    manifest["videos"].insert(0, entry)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


def main() -> None:
    from app.config import settings

    repo_root = settings.STORAGE_DIR.parent
    public_showcase_dir = repo_root / "frontend" / "public" / "showcase"

    parser = argparse.ArgumentParser(description="Promove um job concluido para o showcase.")
    parser.add_argument("job_id")
    parser.add_argument("niche", help="slug do nicho (curiosidades, religioso, ...)")
    parser.add_argument("title")
    parser.add_argument("--phrase", default="")
    parser.add_argument("--before-script", default="")
    parser.add_argument("--hero", action="store_true", help="vai para public/showcase (commitado) e marca hero")
    parser.add_argument("--caption-style", default="tiktok")
    parser.add_argument("--template-label", default=None)
    args = parser.parse_args()

    entry = promote_video(
        args.job_id,
        args.niche,
        args.title,
        output_dir=settings.STORAGE_DIR / "output",
        showcase_storage_dir=settings.STORAGE_DIR / "showcase",
        public_showcase_dir=public_showcase_dir,
        manifest_path=public_showcase_dir / "showcase.json",
        hero=args.hero,
        phrase=args.phrase,
        before_script=args.before_script,
        caption_style=args.caption_style,
        template_label=args.template_label,
    )
    print(f"OK: {entry['video']}  (id={entry['id']}, niche={entry['niche']})")
    print("Valide com: cd frontend && node scripts/check-showcase.mjs && node scripts/check-niche-manifest.mjs")


if __name__ == "__main__":
    main()
