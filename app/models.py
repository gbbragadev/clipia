from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=5, max_length=500)
    style: str = Field(default="educational", pattern="^(educational|curiosity|storytelling|news)$")
    duration_target: int = Field(default=45, ge=20, le=60)


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float = 0.0
    current_step: str | None = None
    error: str | None = None
    created_at: str
    download_url: str | None = None


class CompositionResponse(BaseModel):
    job_id: str
    script: dict
    words: list[dict]
    audio_url: str
    media_urls: list[str]
    subtitle_style: dict
    editor_state: dict | None = None
    fps: int = 30
    width: int = 1080
    height: int = 1920


class EditRequest(BaseModel):
    editor_state: dict


class RegenerateTTSRequest(BaseModel):
    text: str | None = None  # if None, keep current narration
    voice_id: str | None = None
    rate: int | None = None
    pitch: int | None = None


class RegenerateMediaRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=6)


class AISuggestRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    context: dict | None = None
