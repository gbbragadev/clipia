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

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, value: str) -> str:
        if value not in TEMPLATES:
            raise ValueError(ErrorMessages.INVALID_INPUT)
        return value


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
