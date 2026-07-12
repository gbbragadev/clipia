import json
import logging

from app.config import settings
from app.services.llm import complete_text_ex, strip_code_fences
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


DIALOGUE_INSTRUCTION = """

REGRAS DE DIÁLOGO:
- Este vídeo é uma CONVERSA entre 2 personagens: A e B (A começa).
- Cada cena é UMA fala curta, alternando A → B → A → B...
- Cada cena tem o campo "speaker": "A" ou "B".
- Falas naturais e com ritmo de conversa real; juntas, explicam/contam o tema.
"""

FORMAT_ADAPT_INSTRUCTION = """

ADAPTACAO DE FORMATO:
- Se o tema NAO se encaixar na estrutura pedida acima (ex.: tema narrativo ou historia pessoal
  com formato de lista de fatos numerados), ADAPTE a estrutura ao tema mantendo o espirito do
  formato (gancho forte, ritmo, CTA).
- NUNCA invente fatos falsos apenas para preencher o formato.
- A coerencia do roteiro com o tema tem prioridade sobre a estrutura rigida do formato.
"""

TREND_CONTEXT_INSTRUCTION = """

CONTEXTO REAL (tendencia atual — ancore o roteiro nestes fatos/angulos reais, sem inventar dados):
{trend_context}
"""

REFINE_PROMPT = """Voce e um roteirista de videos curtos virais. Melhore o roteiro abaixo seguindo a instrucao do usuario.

INSTRUCAO DO USUARIO: {instruction}

ROTEIRO ATUAL (JSON):
{script_json}

REGRAS:
- Mantenha EXATAMENTE o mesmo formato JSON (mesmos campos por cena; preserve keywords_en/visual_hint/speaker quando existirem)
- Altere APENAS o que a instrucao pede; preserve o resto
- A soma dos duration_hint deve continuar EXATAMENTE {duration} segundos
- A concatenacao dos "text" deve formar a narracao completa (atualize "narration" junto)
- Portugues brasileiro natural; sem emojis

Retorne APENAS o JSON do roteiro melhorado."""


def generate_script(
    topic: str,
    style: str,
    duration_target: int,
    template_id: str = "stock_narration",
    trend_context: str | None = None,
    force_dialogue: bool = False,
) -> dict:
    template = get_template(template_id)
    word_count = int(duration_target * template.script.word_rate)
    # narration_mode="dialogue" liga o roteiro em conversa em templates dialogue_capable
    # sem tocar no preset do template (a sintese usa as 2 vozes de settings.DIALOGUE_VOICE_*)
    is_dialogue = template.script.is_dialogue or force_dialogue

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

    if is_dialogue:
        prompt_text += DIALOGUE_INSTRUCTION
        prompt_text = prompt_text.replace(
            '"duration_hint": 7',
            '"speaker": "A",\n      "duration_hint": 7',
        )

    prompt_text += template.script.prompt_extra

    prompt_text += FORMAT_ADAPT_INSTRUCTION

    if trend_context and trend_context.strip():
        prompt_text += TREND_CONTEXT_INSTRUCTION.format(trend_context=trend_context.strip())

    # max_tokens default de complete_text_ex e alto de proposito (reasoning do DeepSeek V4 Pro).
    raw, llm_provider = complete_text_ex(prompt_text)
    raw = strip_code_fences(raw)
    if not raw:
        raise ScriptValidationError("LLM retornou resposta vazia (reasoning pode ter estourado o max_tokens)")
    script = _parse_script_json(raw)

    # Guardrail anti-burn: clampa o nº de cenas ANTES de _fix_durations (que redistribui a
    # duracao pelas cenas restantes). Cada cena de ai_video/ai_image = 1 geracao PAGA; sem teto,
    # um roteiro com cenas demais (LLM excede as "4-6", ou prompt injection pedindo exaustividade)
    # multiplica o custo com credito fixo. Teto PROPORCIONAL a duracao (>=6, no maximo 1 cena por
    # ~4s) limitado pelo teto duro absoluto — nao corta videos longos legitimos.
    scenes = script.get("scenes")
    if isinstance(scenes, list):
        # ai_video tem teto PROPRIO, mais apertado: cada cena e um clipe Seedance pago
        # de VIDEO_GEN_CLIP_SECONDS (a margem dos 30 creditos assume ~6-8 clipes).
        if template.media.source == "ai_video":
            max_scenes = min(settings.MAX_SCENES_AI_VIDEO, max(6, -(-duration_target // 4)))
        else:
            max_scenes = min(settings.MAX_SCENES_PER_VIDEO, max(6, -(-duration_target // 4)))
        if len(scenes) > max_scenes:
            logger.warning(
                "roteiro com %d cenas clampado para %d (duracao=%ds, template=%s) — anti-burn",
                len(scenes),
                max_scenes,
                duration_target,
                template_id,
            )
            script["scenes"] = scenes[:max_scenes]

    # Metadado de qualidade (Q7): qual provedor da cascata atendeu. Viaja dentro do
    # script (persistido no Postgres via finalize) — degradacao fica visivel sem migration.
    script["llm_provider"] = llm_provider

    # Validate and fix duration_hints
    script = _fix_durations(script, duration_target)
    script = _apply_default_transitions(script)

    # Validate visual_hint presence for templates that require it
    if template.script.needs_visual_hint:
        for i, sc in enumerate(script.get("scenes", [])):
            if not sc.get("visual_hint", "").strip():
                raise ScriptValidationError(f"cena {i + 1} sem visual_hint (template {template_id} exige)")

    # Dialogue: normalize speaker to A/B (default A) so synthesis always has a valid voice
    if is_dialogue:
        for sc in script.get("scenes", []):
            sc["speaker"] = "B" if str(sc.get("speaker", "A")).strip().upper() == "B" else "A"

    return script


def refine_script(script: dict, instruction: str, duration_target: int, template_id: str = "stock_narration") -> dict:
    """Refina um roteiro existente segundo a instrucao do usuario (custa 0,5 credito,
    debitado server-side na rota). Mantem o formato e re-valida duracoes."""
    template = get_template(template_id)
    prompt = REFINE_PROMPT.format(
        instruction=instruction.strip(),
        script_json=json.dumps(script, ensure_ascii=False),
        duration=duration_target,
    )
    raw, llm_provider = complete_text_ex(prompt)
    raw = strip_code_fences(raw)
    if not raw:
        raise ScriptValidationError("LLM retornou resposta vazia no refino")
    refined = _parse_script_json(raw)
    refined["llm_provider"] = llm_provider
    refined = _fix_durations(refined, duration_target)
    refined = _apply_default_transitions(refined)
    if template.script.needs_visual_hint:
        for i, sc in enumerate(refined.get("scenes", [])):
            if not sc.get("visual_hint", "").strip():
                # refino nao pode perder o visual_hint: recupera da cena original correspondente
                original = script.get("scenes") or []
                if i < len(original) and original[i].get("visual_hint"):
                    sc["visual_hint"] = original[i]["visual_hint"]
                else:
                    raise ScriptValidationError(f"cena {i + 1} sem visual_hint apos o refino")
    return refined


def _parse_script_json(raw: str) -> dict:
    """Parse LLM output into a JSON dict, tolerating prose wrapping the JSON object.

    Estrategia defensiva (sem dep de libs tipo json-repair):
    1. Tenta ``json.loads`` direto (caso ideal: LLM respeitou o prompt).
    2. Se falhar, recorta entre o primeiro ``{`` e o ultimo ``}`` (LLM costema envolver
       o JSON em texto explicativo, ex.: "Aqui esta o roteiro:\\n{...}\\nEspero que...").
    3. Se ainda assim nao parsear, levanta ``ScriptValidationError`` com os primeiros 200
       chars do raw para diagnostico (nao loga o raw inteiro — aqui e so roteiro de video,
       mas mantemos o principio de nao vazar payload desconhecido em logs).
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    preview = raw[:200].replace("\n", "\\n")
    raise ScriptValidationError(
        f"LLM retornou JSON invalido (nao foi possivel extrair um objeto JSON). Primeiros 200 chars: {preview}"
    )


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


def _apply_default_transitions(script: dict) -> dict:
    """Cenas novas entram com fade por default (cena 0 nao tem transicao de entrada)."""
    for i, scene in enumerate(script.get("scenes", [])):
        if i > 0 and not scene.get("transition"):
            scene["transition"] = "fade"
    return script
