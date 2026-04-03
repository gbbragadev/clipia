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
