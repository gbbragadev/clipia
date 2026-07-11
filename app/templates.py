"""Video template definitions — controls layout, media, script, and voice for each format."""

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class LayoutConfig:
    type: str  # "fullscreen" | "split_horizontal" | "character_overlay"
    # For split: top region height ratio (0.55 = top 55%, bottom 45%)
    split_ratio: float = 1.0
    character_image: str | None = None  # filename in storage/library/characters/


@dataclass(frozen=True)
class MediaStrategy:
    source: str  # "pexels" | "local" | "ai_image" | "ai_video"
    library_tag: str | None = None  # e.g. "minecraft_parkour"
    loop_single: bool = False  # True = one clip looped for entire video
    # Campos para source == "ai_image":
    image_quality: str = "medium"
    image_size: str = "1024x1536"
    style_suffix: str = ""
    ken_burns: bool = False


@dataclass(frozen=True)
class ScriptConfig:
    prompt_extra: str
    needs_keywords: bool = True
    needs_visual_hint: bool = False
    is_dialogue: bool = False  # roteiro como conversa entre 2 personagens (speaker A/B por cena)
    word_rate: float = 2.05


@dataclass(frozen=True)
class VoicePreset:
    provider: str = "edge"  # "edge" | "elevenlabs" | "custom"
    voice_id: str = "pt-BR-AntonioNeural"
    rate: int = -10
    pitch: int = 5


@dataclass(frozen=True)
class VideoTemplate:
    id: str
    name: str
    description: str
    icon: str
    layout: LayoutConfig
    media: MediaStrategy
    script: ScriptConfig
    voice: VoicePreset
    # Aceita narration_mode="dialogue" (roteiro em conversa + 2 vozes ElevenLabs)?
    # Falso nos formatos de narrador unico bem definidos e no dialogue_duo (ja e nativo).
    dialogue_capable: bool = False


TEMPLATES: dict[str, VideoTemplate] = {
    "stock_narration": VideoTemplate(
        id="stock_narration",
        name="Narração + Stock",
        description="Video clássico com footage relevante e narração",
        icon="🎬",
        layout=LayoutConfig(type="fullscreen"),
        media=MediaStrategy(source="pexels"),
        script=ScriptConfig(
            prompt_extra="",
            needs_keywords=True,
        ),
        voice=VoicePreset(),
        dialogue_capable=True,
    ),
    "curiosidades_lista": VideoTemplate(
        id="curiosidades_lista",
        name="Top Curiosidades",
        description="Lista numerada de fatos surpreendentes com gancho forte — o formato viral clássico",
        icon="🤯",
        layout=LayoutConfig(type="fullscreen"),
        media=MediaStrategy(source="pexels"),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste video e uma LISTA NUMERADA de curiosidades (formato viral 'top N')."
                "\nCena 1 = gancho com promessa explicita (ex: '5 curiosidades sobre X que quase ninguem conhece')."
                "\nCada cena do meio = UM fato numerado em voz alta ('Numero 3: ...'), em ordem crescente"
                " de impacto — guarde o mais insano para a penultima cena."
                "\nUltima cena = CTA rapido ('Comenta qual te surpreendeu e segue para mais')."
                "\nFatos REAIS e verificaveis; se nao tiver certeza, troque o fato."
            ),
            needs_keywords=True,
        ),
        voice=VoicePreset(),
        dialogue_capable=True,
    ),
    "voce_sabia": VideoTemplate(
        id="voce_sabia",
        name="Você Sabia?",
        description="Um único fato surpreendente, curto e direto — perfeito para volume diário",
        icon="💡",
        layout=LayoutConfig(type="fullscreen"),
        media=MediaStrategy(source="pexels"),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste video e do formato 'VOCE SABIA?' — UM unico fato surpreendente, explorado a fundo."
                "\nCena 1 = comece literalmente com 'Voce sabia que' + a parte mais chocante do fato."
                "\nCenas do meio = o porque/como, com detalhes que aumentam a surpresa."
                "\nUltima cena = fechamento memoravel que convida a compartilhar."
                "\nUse no MAXIMO 4 cenas — video curto e denso."
                "\nFato REAL e verificavel; se nao tiver certeza, troque o fato."
            ),
            needs_keywords=True,
            word_rate=2.0,
        ),
        voice=VoicePreset(voice_id="pt-BR-ThalitaNeural", rate=-5, pitch=2),
    ),
    "gameplay_split": VideoTemplate(
        id="gameplay_split",
        name="Gameplay Split",
        description="Fatos/história em cima, gameplay embaixo (Minecraft, Subway Surfers)",
        icon="🎮",
        layout=LayoutConfig(type="split_horizontal", split_ratio=0.55),
        media=MediaStrategy(source="local", library_tag="cinematic", loop_single=False),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste video usa formato SPLIT SCREEN — texto em cima, trecho de filme/serie embaixo."
                "\nNAO inclua keywords_en (o video de fundo sera clipe cinematografico)."
                "\nFoque em fatos curtos e impactantes, estilo lista numerada."
                "\nCada cena = 1 fato. Frases MUITO curtas (max 10 palavras)."
            ),
            needs_keywords=False,
            word_rate=1.8,
        ),
        voice=VoicePreset(voice_id="pt-BR-AntonioNeural", rate=-5, pitch=0),
    ),
    "character_narration": VideoTemplate(
        id="character_narration",
        name="Personagem Narrador",
        description="Personagem IA explica o tema com fundo satisfying",
        icon="🗣️",
        layout=LayoutConfig(
            type="character_overlay",
            character_image="peter_griffin.png",
        ),
        media=MediaStrategy(source="local", library_tag="satisfying", loop_single=False),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste video tem um PERSONAGEM narrando (estilo Peter Griffin)."
                "\nTom COMICO e informal. Use humor, exageros, e comparacoes absurdas."
                "\nNAO inclua keywords_en (o fundo sera video satisfying)."
                "\nFrases curtas, dramaticas. Pausa entre ideias."
                "\nComece com algo tipo 'Ei, voce sabia que...' ou 'Cara, isso e INSANO...'"
            ),
            needs_keywords=False,
            word_rate=1.7,
        ),
        voice=VoicePreset(voice_id="pt-BR-AntonioNeural", rate=-15, pitch=-3),
    ),
    "story_time": VideoTemplate(
        id="story_time",
        name="Story Time",
        description="História narrada com gameplay/satisfying no fundo, estilo Reddit",
        icon="📖",
        layout=LayoutConfig(type="split_horizontal", split_ratio=0.50),
        media=MediaStrategy(source="local", library_tag="satisfying", loop_single=False),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste video e uma HISTORIA narrada (estilo Reddit stories)."
                "\nNAO inclua keywords_en (o fundo sera video satisfying/gameplay)."
                "\nConte a historia em primeira pessoa quando possivel."
                "\nCrie tensao e suspense. Revele informacao aos poucos."
                "\nUse 6 cenas para ter mais desenvolvimento."
            ),
            needs_keywords=False,
            word_rate=2.1,
        ),
        voice=VoicePreset(voice_id="pt-BR-FranciscaNeural", rate=-5, pitch=0),
        dialogue_capable=True,
    ),
    "novelinha_historica": VideoTemplate(
        id="novelinha_historica",
        name="Drama Histórico",
        description="Fatos reais narrados como trailer cinematográfico, com imagens IA",
        icon="🎭",
        layout=LayoutConfig(type="fullscreen"),
        media=MediaStrategy(
            source="ai_image",
            image_quality="medium",
            image_size="1024x1536",
            style_suffix=(
                "fotografia de época ou ilustração cinematográfica realista, "
                "iluminação dramática, composição vertical 2:3, "
                "sem texto na imagem, sem marca d'água"
            ),
            ken_burns=True,
        ),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste vídeo é um DRAMA HISTÓRICO narrado como trailer cinematográfico."
                "\nBase-se em um FATO REAL curioso, macabro ou pouco conhecido."
                "\nArco narrativo obrigatório: GANCHO (cena 1) → CONTEXTO (cenas 2-3) → "
                "CLÍMAX (cenas 4-5) → TWIST/RESOLUÇÃO (cena 6)."
                "\nTom grave, pausado, ligeiramente teatral — narrador de documentário."
                "\nUse EXATAMENTE 6 cenas, ~5 segundos cada."
                "\nNÃO invente fatos — se não sabe, escolha outro evento."
            ),
            needs_keywords=False,
            needs_visual_hint=True,
            word_rate=1.8,
        ),
        voice=VoicePreset(
            provider="elevenlabs",
            voice_id="KHmfNHtEjHhLK9eER20w",  # Fernanda (pt-BR). Swap em Task 17 se quiser outra voz.
            rate=-10,
            pitch=-2,
        ),
        dialogue_capable=True,
    ),
    "ai_visual": VideoTemplate(
        id="ai_visual",
        name="Imagens IA",
        description="Narração com imagens geradas por IA para qualquer tema, com efeito Ken Burns",
        icon="🖼️",
        layout=LayoutConfig(type="fullscreen"),
        media=MediaStrategy(
            source="ai_image",
            image_quality="medium",
            image_size="1024x1536",
            style_suffix=(
                "ilustração digital cinematográfica de alta qualidade, composição vertical 2:3, "
                "iluminação rica, cores marcantes, foco nítido, "
                "sem texto na imagem, sem marca d'água"
            ),
            ken_burns=True,
        ),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste vídeo usa IMAGENS GERADAS POR IA (uma por cena)."
                "\nCada cena precisa de um visual_hint concreto e visualmente rico,"
                " adequado ao tema (não precisa ser histórico)."
            ),
            needs_keywords=False,
            needs_visual_hint=True,
            word_rate=1.9,
        ),
        voice=VoicePreset(),  # Edge default (mais barato que ElevenLabs)
        dialogue_capable=True,
    ),
    "ai_video": VideoTemplate(
        id="ai_video",
        name="Vídeo IA (premium)",
        description="Cenas em vídeo geradas por IA (movimento real) para qualquer tema — o formato mais premium",
        icon="🎞️",
        layout=LayoutConfig(type="fullscreen"),
        media=MediaStrategy(
            source="ai_video",
            # style_suffix vira sufixo do prompt de cada clipe (modelos de video premiam descricao de movimento/camera)
            style_suffix=(
                "movimento de câmera cinematográfico suave, iluminação dramática, "
                "alta qualidade, foco nítido, vertical 9:16, sem texto na tela, sem marca d'água"
            ),
        ),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste vídeo usa CENAS GERADAS EM VÍDEO POR IA (uma por cena)."
                "\nCada cena precisa de um visual_hint concreto, visualmente rico e COM MOVIMENTO"
                " implícito (ação, câmera, dinâmica) — não uma foto estática."
            ),
            needs_keywords=False,
            needs_visual_hint=True,
            word_rate=1.9,
        ),
        voice=VoicePreset(),  # Edge default; o video ja e o custo dominante
    ),
    "dialogue_duo": VideoTemplate(
        id="dialogue_duo",
        name="Diálogo (2 vozes)",
        description="Conversa entre dois personagens com vozes distintas e fundo dinâmico",
        icon="💬",
        layout=LayoutConfig(type="split_horizontal", split_ratio=0.55),
        media=MediaStrategy(source="local", library_tag="podcast", loop_single=False),
        script=ScriptConfig(
            prompt_extra="",
            needs_keywords=False,
            is_dialogue=True,
            word_rate=2.0,
        ),
        # As 2 vozes reais vêm de settings.DIALOGUE_VOICE_A/B na síntese; provider elevenlabs p/ pricing
        voice=VoicePreset(provider="elevenlabs", voice_id=settings.DIALOGUE_VOICE_A),
    ),
}


def get_template(template_id: str) -> VideoTemplate:
    """Get template by ID, defaulting to stock_narration."""
    return TEMPLATES.get(template_id, TEMPLATES["stock_narration"])
