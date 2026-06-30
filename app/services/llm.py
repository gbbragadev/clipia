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


def _call(model: str, prompt: str, max_tokens: int, json_mode: bool) -> str:
    client = get_client()
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    completion = client.chat.completions.create(**kwargs)
    return completion.choices[0].message.content or ""


def complete_text(prompt: str, max_tokens: int = 16000, json_mode: bool = True) -> str:
    """Faz uma chamada de chat completion e retorna o texto da resposta.

    json_mode=True pede response_format JSON (o prompt deve mencionar JSON).
    max_tokens ALTO de proposito: o DeepSeek V4 Pro e modelo de reasoning e gasta
    tokens "pensando" antes do output. Com budget baixo (ex. 4096) o reasoning
    consome tudo (finish_reason=length) e o content volta vazio. O modelo para em
    finish=stop quando termina, entao o teto alto nao custa tokens extras.

    Se o modelo principal falhar (cota estourada / erro) e LLM_FALLBACK_MODEL estiver
    setado, tenta uma vez no modelo FREE de fallback antes de propagar o erro.
    """
    try:
        result = _call(settings.LLM_MODEL, prompt, max_tokens, json_mode)
        if result:
            return result
        raise ValueError("modelo retornou resposta vazia (reasoning exauriu max_tokens)")
    except Exception as e:
        if not settings.LLM_FALLBACK_MODEL:
            raise
        logger.warning(
            "LLM principal (%s) falhou: %s — tentando fallback FREE %s",
            settings.LLM_MODEL,
            e,
            settings.LLM_FALLBACK_MODEL,
        )
        return _call(settings.LLM_FALLBACK_MODEL, prompt, max_tokens, json_mode)
