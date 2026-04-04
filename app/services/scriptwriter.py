import json
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

SCRIPT_PROMPT = """Voce e um roteirista de videos curtos virais (YouTube Shorts, Reels, TikTok).

Crie um roteiro sobre: {topic}
Estilo: {style}
Duracao EXATA: {duration} segundos
Palavras na narracao: EXATAMENTE {word_count} palavras (isso e critico — conte as palavras)
Idioma: Portugues brasileiro natural e coloquial

ESTRUTURA OBRIGATORIA:
- Cena 1 (3-5s): GANCHO — pergunta provocativa ou fato chocante que prende nos primeiros 3 segundos
- Cenas 2 a N-1: DESENVOLVIMENTO — cada cena entrega um fato/insight, construindo interesse crescente
- Ultima cena (3-5s): CONCLUSAO — fechamento memoravel ou chamada para acao

REGRAS DE DURACAO:
- A soma dos duration_hint de TODAS as cenas DEVE ser EXATAMENTE {duration} segundos
- Cada cena deve ter entre 4 e 12 segundos
- Divida em 4-6 cenas

REGRAS DE NARRACAO:
- Escreva como se estivesse CONVERSANDO com o espectador, nao lendo um texto
- Use frases curtas e diretas (max 15 palavras por frase)
- Varie o ritmo: alterne frases curtas impactantes com explicacoes breves
- NAO use emojis
- O campo "text" de cada cena deve conter o TRECHO EXATO da narracao correspondente aquela cena
- A concatenacao de todos os "text" deve formar a narracao completa

REGRAS DE KEYWORDS:
- Keywords em INGLES para busca de video stock no Pexels
- Sejam ESPECIFICAS e VISUAIS: "orange tabby cat close up face" NAO "cat"
- 3-4 keywords descritivas por cena que resultem em video PORTRAIT relevante
- Prefira: animais em close, paisagens dramaticas, macro shots, acoes humanas

Retorne APENAS JSON valido:
{{
  "title": "titulo curto chamativo (max 8 palavras)",
  "narration": "texto completo da narracao",
  "scenes": [
    {{
      "text": "trecho exato da narracao para esta cena",
      "keywords_en": ["specific", "visual", "search terms"],
      "duration_hint": 7
    }}
  ],
  "hashtags": ["#shorts", "#relevante"]
}}"""


def generate_script(topic: str, style: str, duration_target: int) -> dict:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    word_count = int(duration_target * 2.05)  # pt-BR at ~2.0 wps, trim/pad handles the rest

    message = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": SCRIPT_PROMPT.format(
                topic=topic,
                style=style,
                duration=duration_target,
                word_count=word_count,
            ),
        }],
    )

    raw = message.content[0].text
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    script = json.loads(raw)

    # Validate and fix duration_hints
    script = _fix_durations(script, duration_target)
    return script


def _fix_durations(script: dict, target: int) -> dict:
    """Ensure scene duration_hints sum to target duration."""
    scenes = script.get("scenes", [])
    if not scenes:
        return script

    total = sum(s.get("duration_hint", 7) for s in scenes)
    if abs(total - target) <= 3:
        return script  # close enough

    # Scale proportionally
    ratio = target / total
    for scene in scenes:
        scene["duration_hint"] = max(3, round(scene["duration_hint"] * ratio))

    # Fix rounding remainder
    new_total = sum(s["duration_hint"] for s in scenes)
    diff = target - new_total
    if diff != 0:
        scenes[-1]["duration_hint"] += diff

    logger.info(f"Fixed durations: {total}s -> {target}s (ratio={ratio:.2f})")
    return script
