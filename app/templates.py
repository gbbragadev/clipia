"""Video template definitions — controls layout, media, script, and voice for each format."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutConfig:
    type: str  # "fullscreen" | "split_horizontal" | "character_overlay"
    # For split: top region height ratio (0.55 = top 55%, bottom 45%)
    split_ratio: float = 1.0
    character_image: str | None = None  # filename in storage/library/characters/


@dataclass(frozen=True)
class MediaStrategy:
    source: str  # "pexels" | "local" | "ai_image"
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
    word_rate: float = 2.05


@dataclass(frozen=True)
class VoicePreset:
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
    ),
    "gameplay_split": VideoTemplate(
        id="gameplay_split",
        name="Gameplay Split",
        description="Fatos/história em cima, gameplay embaixo (Minecraft, Subway Surfers)",
        icon="🎮",
        layout=LayoutConfig(type="split_horizontal", split_ratio=0.55),
        media=MediaStrategy(source="local", library_tag="minecraft_parkour", loop_single=True),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste video usa formato SPLIT SCREEN — texto em cima, gameplay embaixo."
                "\nNAO inclua keywords_en (o video de fundo sera gameplay)."
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
        description="Personagem IA explica o tema com gameplay ou fundo simples",
        icon="🗣️",
        layout=LayoutConfig(
            type="character_overlay",
            character_image="peter_griffin.png",
        ),
        media=MediaStrategy(source="local", library_tag="minecraft_parkour", loop_single=True),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste video tem um PERSONAGEM narrando (estilo Peter Griffin)."
                "\nTom COMICO e informal. Use humor, exageros, e comparacoes absurdas."
                "\nNAO inclua keywords_en (o fundo sera gameplay generico)."
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
        media=MediaStrategy(source="local", library_tag="satisfying", loop_single=True),
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
    ),
}


def get_template(template_id: str) -> VideoTemplate:
    """Get template by ID, defaulting to stock_narration."""
    return TEMPLATES.get(template_id, TEMPLATES["stock_narration"])
