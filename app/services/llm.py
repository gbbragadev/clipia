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
    """Cliente OpenAI apontado para o OpenRouter (compat — usado por chamadas legadas)."""
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


def _provider_chain() -> list[tuple[str, str, str, str]]:
    """Cascata de provedores (label, model, base_url, api_key) tentados EM ORDEM.

    Ordem = cascata de budget do dono: OpenRouter pago -> OpenAI -> xAI -> OpenRouter free.
    Provedores sem key sao omitidos. Todos expoem API compativel com OpenAI.
    """
    chain: list[tuple[str, str, str, str]] = []
    # OpenAI PRIMARIO (30/06): o saldo pago do OpenRouter foi zerado (Seedance/vídeo IA queimou ~$6).
    # OpenRouter pago fica DEPOIS — volta automatico se recarregar. Pra retomar DeepSeek como primario,
    # recarregue o OpenRouter ou mova o bloco dele pra cima.
    openai_key = settings.LLM_OPENAI_KEY or settings.OPENAI_API_KEY
    if openai_key:
        chain.append(("openai", settings.LLM_OPENAI_MODEL, settings.OPENAI_BASE_URL, openai_key))
    if settings.LLM_XAI_KEY:
        chain.append(("xai", settings.LLM_XAI_MODEL, settings.LLM_XAI_BASE_URL, settings.LLM_XAI_KEY))
    if settings.OPEN_ROUTER_API_KEY:
        chain.append(("openrouter", settings.LLM_MODEL, settings.OPENROUTER_BASE_URL, settings.OPEN_ROUTER_API_KEY))
    if settings.OPEN_ROUTER_API_KEY and settings.LLM_FALLBACK_MODEL:
        chain.append(
            ("openrouter-free", settings.LLM_FALLBACK_MODEL, settings.OPENROUTER_BASE_URL, settings.OPEN_ROUTER_API_KEY)
        )
    return chain


def _call(model: str, prompt: str, max_tokens: int, json_mode: bool, base_url: str, api_key: str) -> str:
    client = openai.OpenAI(base_url=base_url, api_key=api_key)
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
    """Chat completion via cascata de provedores; retorna o texto da PRIMEIRA resposta nao-vazia.

    json_mode=True pede response_format JSON (o prompt deve mencionar JSON).
    max_tokens ALTO de proposito: modelos de reasoning (DeepSeek V4 Pro) gastam tokens "pensando"
    antes do output; com teto baixo o content volta vazio (finish_reason=length).

    A cascata (_provider_chain) tenta OpenRouter pago -> OpenAI -> xAI -> OpenRouter free. Pula
    provedor que erra (ex.: 402 sem credito) OU devolve vazio, ate um responder. Se todos
    falharem, levanta o ultimo erro (nunca retorna "" silencioso).
    """
    chain = _provider_chain()
    if not chain:
        raise RuntimeError("Nenhum provedor LLM configurado (defina OPEN_ROUTER_API_KEY/LLM_OPENAI_KEY/etc.)")

    last_err: Exception | None = None
    for label, model, base_url, api_key in chain:
        try:
            result = _call(model, prompt, max_tokens, json_mode, base_url, api_key)
            if result and result.strip():
                if label != "openrouter":
                    logger.info("LLM atendido pelo provedor de fallback: %s (%s)", label, model)
                return result
            last_err = ValueError(f"{label}/{model} retornou resposta vazia")
            logger.warning("LLM %s (%s) vazio — proximo provedor", label, model)
        except Exception as e:  # noqa: BLE001 — segue a cascata em qualquer falha do provedor
            last_err = e
            logger.warning("LLM %s (%s) falhou: %s — proximo provedor", label, model, e)

    raise last_err or RuntimeError("Todos os provedores LLM falharam")
