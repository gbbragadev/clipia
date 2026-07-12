from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth.schemas import _normalize_email
from app.errors import ErrorMessages, json_size_bytes
from app.templates import TEMPLATES


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=10, max_length=500, description="The main topic of the video")
    style: Literal["educational", "storytelling", "news", "comedy"] = Field(
        default="educational", description="The style/tone of the video"
    )
    duration_target: int = Field(default=45, ge=15, le=180, description="Target duration in seconds")
    template_id: str = Field(default="stock_narration", description="Template to use for the video")
    voice_provider: Literal["edge", "elevenlabs", "custom"] = Field(default="edge", description="Voice provider to use")
    voice_config: dict | None = Field(default=None, description="Voice configuration (voice_id, rate, pitch, etc)")
    trend_context: str | None = Field(
        default=None,
        max_length=2000,
        description="Dados reais da tendencia (titulo + contexto) para fundamentar o roteiro",
    )
    sfx_enabled: bool | None = Field(
        default=None, description="Liga/desliga SFX (whoosh) por video. None = usar settings.SFX_ENABLED"
    )
    music_enabled: bool | None = Field(
        default=None, description="Liga/desliga musica de fundo por video. None = usar settings.AUTO_MUSIC_ENABLED"
    )
    narration_mode: Literal["single", "dialogue"] = Field(
        default="single",
        description="dialogue = roteiro em conversa + 2 vozes ElevenLabs (so em templates dialogue_capable)",
    )
    custom_script: dict | None = Field(
        default=None,
        description="Roteiro pronto (do /script-preview, possivelmente editado) — pula a geracao de roteiro",
    )

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, value: str) -> str:
        if value not in TEMPLATES:
            raise ValueError(ErrorMessages.INVALID_INPUT)
        return value

    @model_validator(mode="after")
    def validate_narration_mode(self):
        if self.narration_mode == "dialogue":
            template = TEMPLATES.get(self.template_id)
            # dialogue_duo ja e dialogo nativo (is_dialogue) — pedir o modo la e redundante mas valido
            if template and not (template.dialogue_capable or template.script.is_dialogue):
                raise ValueError(ErrorMessages.INVALID_INPUT)
        return self

    @model_validator(mode="after")
    def validate_custom_script(self):
        if self.custom_script is not None:
            if json_size_bytes(self.custom_script) > 100 * 1024:
                raise ValueError(ErrorMessages.INVALID_INPUT)
            scenes = self.custom_script.get("scenes")
            narration = self.custom_script.get("narration")
            if not isinstance(scenes, list) or not scenes or not isinstance(narration, str) or not narration.strip():
                raise ValueError(ErrorMessages.INVALID_INPUT)

            # O caminho custom PULA o generate_script, entao os guardrails de la
            # precisam valer AQUI (achado da revisao): sem o teto de cenas, um roteiro
            # editado com N cenas num template de imagem/video IA = N geracoes PAGAS.
            from app.config import settings

            template = TEMPLATES.get(self.template_id)
            # ai_video tem teto PROPRIO de cenas: cada cena e um clipe Seedance pago
            # (o teto global proporcional a duracao chega a 40 e estoura a margem).
            if template is not None and template.media.source == "ai_video":
                max_scenes = min(settings.MAX_SCENES_AI_VIDEO, max(6, -(-self.duration_target // 4)))
            else:
                max_scenes = min(settings.MAX_SCENES_PER_VIDEO, max(6, -(-self.duration_target // 4)))
            if len(scenes) > max_scenes:
                raise ValueError(ErrorMessages.INVALID_INPUT)

            needs_hint = bool(template and template.script.needs_visual_hint)
            is_dialogue = self.narration_mode == "dialogue" or bool(template and template.script.is_dialogue)
            for sc in scenes:
                if not isinstance(sc, dict) or not str(sc.get("text", "")).strip():
                    raise ValueError(ErrorMessages.INVALID_INPUT)
                if needs_hint and not str(sc.get("visual_hint", "")).strip():
                    raise ValueError(ErrorMessages.INVALID_INPUT)
                if is_dialogue:
                    # normaliza speaker A/B (a sintese de dialogo exige um dos dois)
                    sc["speaker"] = "B" if str(sc.get("speaker", "A")).strip().upper() == "B" else "A"
        return self


class ScriptRefineRequest(BaseModel):
    script: dict = Field(..., description="Roteiro atual (formato do /script-preview)")
    instruction: str = Field(
        ..., min_length=5, max_length=500, description="O que melhorar (ex: 'deixe a cena 2 mais dramática')"
    )
    duration_target: int = Field(default=45, ge=15, le=180)
    template_id: str = Field(default="stock_narration")

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, value: str) -> str:
        if value not in TEMPLATES:
            raise ValueError(ErrorMessages.INVALID_INPUT)
        return value

    @model_validator(mode="after")
    def validate_script_size(self):
        if json_size_bytes(self.script) > 100 * 1024:
            raise ValueError(ErrorMessages.INVALID_INPUT)
        return self


class VoiceCloneRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name for the cloned voice")
    description: str = Field(default="", max_length=500)


class VoiceDesignRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Nome da voz a criar")
    description: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Descrição da voz (ex: 'narrador grave e misterioso, ritmo pausado')",
    )
    text: str | None = Field(default=None, max_length=1000, description="Texto de amostra (opcional)")


class JobStatus(BaseModel):
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Current job status")
    progress: float = Field(default=0.0, description="Job progress percentage")
    current_step: str | None = Field(default=None, description="Current processing step")
    error: str | None = Field(default=None, description="Error message if failed")
    detail: str | None = Field(default=None, description="Detailed status information")
    created_at: str = Field(..., description="Job creation timestamp")
    download_url: str | None = Field(default=None, description="URL to download the final video")


class CompositionResponse(BaseModel):
    job_id: str = Field(..., description="Job ID")
    script: dict = Field(..., description="Video script data")
    words: list[dict] = Field(..., description="Word timestamps for subtitles")
    audio_url: str = Field(..., description="URL to narration audio")
    media_urls: list[str] = Field(..., description="URLs to media assets")
    subtitle_style: dict = Field(..., description="Subtitle styling configuration")
    editor_state: dict | None = Field(default=None, description="Saved editor state")
    template_id: str = Field(default="stock_narration", description="Template ID")
    layout_type: str = Field(default="fullscreen", description="Layout type")
    fps: int = Field(default=30, description="Frames per second")
    width: int = Field(default=1080, description="Video width")
    height: int = Field(default=1920, description="Video height")
    pending_credits: float = Field(default=0.0, description="Pending credits cost")
    music_url: str | None = Field(default=None, description="Faixa de fundo do mood (default quando sem editor_state)")
    music_volume: float = Field(default=0.12, description="Volume default da musica de fundo")


class EditRequest(BaseModel):
    editor_state: dict = Field(..., description="New editor state to save")


class RegenerateTTSRequest(BaseModel):
    text: str | None = Field(
        default=None, max_length=5000, description="New text for narration"
    )  # if None, keep current narration
    voice_id: str | None = Field(default=None, description="Voice ID to use (Edge or ElevenLabs)")
    voice_provider: Literal["edge", "elevenlabs"] = Field(default="edge", description="Provider for regeneration")
    rate: int | None = Field(default=None, ge=-50, le=50)
    pitch: int | None = Field(default=None, ge=-50, le=50)


class RegenerateMediaRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=6, description="Keywords to generate media")


class AISuggestRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="User instruction for AI")
    context: dict | None = None

    @model_validator(mode="after")
    def validate_context_size(self):
        if self.context is not None and json_size_bytes(self.context) > 100 * 1024:
            raise ValueError(ErrorMessages.INVALID_INPUT)
        return self


class WaitlistRequest(BaseModel):
    email: str = Field(..., description="Email to join waitlist")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        return _normalize_email(value)


class FeedbackRequest(BaseModel):
    kind: Literal["widget", "post_video"]
    rating: int | None = Field(None, ge=1, le=5, description="Nota 1-5 (widget) ou 1/5 = 👎/👍 (pos-video)")
    comment: str | None = Field(None, max_length=1000)
    job_id: str | None = None
    source_url: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_has_content(self):
        if self.rating is None and not (self.comment or "").strip():
            raise ValueError(ErrorMessages.INVALID_INPUT)
        return self


class AdminCreditAdjustRequest(BaseModel):
    delta: int = Field(..., ge=-100_000, le=100_000, description="Creditos a somar (negativo subtrai)")
    reason: str = Field(..., min_length=3, max_length=255, description="Motivo do ajuste (auditoria)")

    @model_validator(mode="after")
    def validate_delta_nonzero(self):
        if self.delta == 0:
            raise ValueError(ErrorMessages.INVALID_INPUT)
        return self
