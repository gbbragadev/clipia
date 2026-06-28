"""Rerank semantico de midia via CLIP (opt-in, MEDIA_RERANK='clip').

Embedda a thumbnail de cada candidato Pexels + o texto/visual_hint da cena e pontua por
similaridade visual. Roda na GPU ociosa (ASR migrou p/ Groq API).

ponytail: reranker plugavel atras de media.order_candidates — heuristica e o default; isto
so e chamado quando MEDIA_RERANK='clip'. Imports pesados (torch/sentence-transformers/PIL)
sao lazy: o modulo importa mesmo sem a dep, e media._clip_scores cai na heuristica se faltar.
Dep opcional: `pip install sentence-transformers` (~2GB com torch).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_model = None


def _minmax_norm(values: list[float]) -> list[float]:
    """Normaliza para 0..1 (min-max) para combinar com os pesos da heuristica."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    return [(v - lo) / span for v in values]


def _get_model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = SentenceTransformer("clip-ViT-B-32", device=device)
        logger.info("CLIP clip-ViT-B-32 carregado em %s", device)
    return _model


def _load_image(url: str):
    from io import BytesIO

    import httpx
    from PIL import Image

    try:
        r = httpx.get(url, timeout=10.0, follow_redirects=True)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as e:  # noqa: BLE001 — thumb que falha so nao pontua
        logger.warning("CLIP: thumb falhou %s: %s", url, e)
        return None


def score_candidates(text: str, candidates: list[dict]) -> dict[str, float]:
    """url -> similaridade 0..1. {} se nao houver texto/thumbs validas."""
    cands = [c for c in candidates if c.get("thumb")]
    if not text or not cands:
        return {}

    images, valid = [], []
    for c in cands:
        img = _load_image(c["thumb"])
        if img is not None:
            images.append(img)
            valid.append(c)
    if not valid:
        return {}

    model = _get_model()
    txt_emb = model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
    img_emb = model.encode(images, convert_to_numpy=True, normalize_embeddings=True)
    sims = (img_emb @ txt_emb[0]).tolist()  # cosine (embeddings normalizados)
    normed = _minmax_norm(sims)
    return {c["url"]: float(s) for c, s in zip(valid, normed)}
