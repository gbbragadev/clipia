"""Cliente LLM — OpenRouter (API compativel com OpenAI).

Substitui o SDK Anthropic na geracao de roteiro e na IA do editor.
O OpenRouter expoe a API compativel com OpenAI; usamos o modelo configurado
em settings.LLM_MODEL (default DeepSeek V4 Pro).
"""

import logging

import openai

from app.config import settings

logger = logging.getLogger(__name__)


def get_client() -> openai.OpenAI:
    """Cliente OpenAI apontado para o OpenRouter."""
    return openai.OpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPEN_ROUTER_API_KEY,
    )


def strip_code_fences(raw: str) -> str:
    """Remove cercas markdown ```...``` que alguns modelos adicionam ao redor do JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return raw


def complete_text(prompt: str, max_tokens: int = 2048, json_mode: bool = True) -> str:
    """Faz uma chamada de chat completion e retorna o texto da resposta.

    json_mode=True pede response_format JSON (o prompt deve mencionar JSON).
    max_tokens generoso para acomodar tokens de reasoning do DeepSeek V4 sem
    truncar a resposta final.
    """
    client = get_client()
    kwargs: dict = {
        "model": settings.LLM_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    completion = client.chat.completions.create(**kwargs)
    return completion.choices[0].message.content or ""
