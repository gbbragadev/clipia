"""Geracao de video IA via OpenRouter (API assincrona /api/v1/videos).

Fluxo (doc: https://openrouter.ai/docs/guides/overview/multimodal/video-generation):
  1. POST /api/v1/videos                -> job id
  2. GET  /api/v1/videos/{id}           -> poll ate status terminal
  3. GET  /api/v1/videos/{id}/content   -> baixa o mp4

Preco e por TOKEN (w*h*dur*24/1024), nao por segundo fixo — ver nota em config.py.
Os clipes das cenas geram em paralelo (asyncio.gather): o gargalo e o clipe mais lento,
nao a soma. Modelo/resolucao/duracao vem de settings (env), trocaveis sem deploy.

ponytail: text-to-video direto (visual_hint -> clipe). first_frame (animar imagem gpt-image)
fica para depois. Os nomes de campo da resposta seguem a doc; como gerar custa $, validar
1x ao vivo antes de produzir em massa (smoke real) — defensivo com .get/fallback ate la.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://openrouter.ai/api/v1/videos"


class VideoGenError(Exception):
    """Falha terminal na geracao de video."""


# ---------- lógica pura (testável offline) ----------


def build_submit_body(prompt: str, duration: int, *, model: str, resolution: str, aspect_ratio: str) -> dict:
    return {
        "model": model,
        "prompt": prompt,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "duration": duration,
        "generate_audio": False,  # ClipIA narra com TTS proprio; nao paga/usa audio do modelo
    }


def classify_status(status: str) -> str:
    """-> 'done' | 'failed' | 'pending'."""
    s = (status or "").lower()
    if s in {"completed", "succeeded", "success"}:
        return "done"
    if s in {"failed", "cancelled", "canceled", "expired", "error"}:
        return "failed"
    return "pending"  # pending/processing/queued/in_progress/...


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.OPEN_ROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


# ---------- rede ----------


async def _generate_clip(client: httpx.AsyncClient, prompt: str, output_path: str, duration: int) -> str:
    body = build_submit_body(
        prompt,
        duration,
        model=settings.OPENROUTER_VIDEO_MODEL,
        resolution=settings.VIDEO_GEN_RESOLUTION,
        aspect_ratio=settings.VIDEO_GEN_ASPECT_RATIO,
    )
    r = await client.post(_BASE, json=body, headers=_headers())
    r.raise_for_status()
    job = r.json()
    job_id = job.get("id") or job.get("job_id")
    if not job_id:
        raise VideoGenError(f"submit sem job id: {job}")

    start = time.monotonic()
    while time.monotonic() - start < settings.VIDEO_GEN_TIMEOUT:
        await asyncio.sleep(settings.VIDEO_GEN_POLL_INTERVAL)
        pr = await client.get(f"{_BASE}/{job_id}", headers=_headers())
        pr.raise_for_status()
        data = pr.json()
        st = classify_status(data.get("status", ""))
        if st == "done":
            break
        if st == "failed":
            raise VideoGenError(f"job {job_id} falhou: {data.get('error') or data}")
    else:
        raise VideoGenError(f"job {job_id} expirou o timeout de {settings.VIDEO_GEN_TIMEOUT}s")

    dr = await client.get(f"{_BASE}/{job_id}/content", headers=_headers(), params={"index": 0})
    dr.raise_for_status()
    Path(output_path).write_bytes(dr.content)
    logger.info("video IA: cena salva em %s (%d bytes)", output_path, len(dr.content))
    return output_path


async def generate_scenes(prompts: list[str], out_dir: str, duration: int | None = None) -> list[str]:
    """Gera 1 clipe por prompt em paralelo. Retorna os paths na ordem das cenas."""
    dur = duration or settings.VIDEO_GEN_CLIP_SECONDS
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # timeout do client cobre 1 request; o poll tem seu proprio teto via VIDEO_GEN_TIMEOUT
    async with httpx.AsyncClient(timeout=120.0) as client:
        tasks = [_generate_clip(client, p, str(out / f"scene_{i}.mp4"), dur) for i, p in enumerate(prompts)]
        return await asyncio.gather(*tasks)
