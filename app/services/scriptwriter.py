import json
import logging

from app.services.llm import complete_text, strip_code_fences
from app.templates import get_template

logger = logging.getLogger(__name__)


class ScriptValidationError(Exception):
    """Raised when script output does not meet template requirements."""


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

VISUAL_HINT_INSTRUCTION = """

REGRAS DE VISUAL_HINT:
- Cada cena tem campo "visual_hint": descricao em portugues de uma imagem unica
- Deve ser CONCRETA: objetos, pessoas, ambiente, iluminacao, angulo
- Evite texto, logos, rostos em close extremo
- Cenas diferentes = imagens claramente diferentes (sem repeticao visual)
- Exemplo bom: "salao vitoriano iluminado por velas, mesa comprida, mulher de vestido escuro olhando pela janela"
- Exemplo ruim: "a mulher" (faltam cena, ambiente, composicao)
"""


def generate_script(topic: str, style: str, duration_target: int, template_id: str = "stock_narration") -> dict:
    template = get_template(template_id)
    word_count = int(duration_target * template.script.word_rate)

    prompt_text = SCRIPT_PROMPT.format(
        topic=topic,
        style=style,
        duration=duration_target,
        word_count=word_count,
    )

    # Remove keywords instructions for templates that don't need them
    if not template.script.needs_keywords:
        prompt_text = prompt_text.replace(
            '"keywords_en": ["specific", "visual", "search terms"],\n      ',
            "",
        )
        prompt_text = prompt_text.replace(
            "REGRAS DE KEYWORDS:\n"
            "- Keywords em INGLES para busca de video stock no Pexels\n"
            '- Sejam ESPECIFICAS e VISUAIS: "orange tabby cat close up face" NAO "cat"\n'
            "- 3-4 keywords descritivas por cena que resultem em video PORTRAIT relevante\n"
            "- Prefira: animais em close, paisagens dramaticas, macro shots, acoes humanas",
            "KEYWORDS: NAO inclua keywords_en neste formato.",
        )

    if template.script.needs_visual_hint:
        prompt_text += VISUAL_HINT_INSTRUCTION
        prompt_text = prompt_text.replace(
            '"duration_hint": 7',
            '"visual_hint": "descricao concreta da cena",\n      "duration_hint": 7',
        )

    prompt_text += template.script.prompt_extra

    raw = complete_text(prompt_text, max_tokens=4096)
    raw = strip_code_fences(raw)
    script = json.loads(raw)

    # Validate and fix duration_hints
    script = _fix_durations(script, duration_target)

    # Validate visual_hint presence for templates that require it
    if template.script.needs_visual_hint:
        for i, sc in enumerate(script.get("scenes", [])):
            if not sc.get("visual_hint", "").strip():
                raise ScriptValidationError(f"cena {i+1} sem visual_hint (template {template_id} exige)")

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
