from pydantic import UUID4, BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicShareCreated(StrictModel):
    token: str
    url: str
    title: str
    active: bool


class PublicShareMetadata(StrictModel):
    title: str
    video_url: str
    active: bool


class QualifiedViewRequest(StrictModel):
    anonymous_session_id: UUID4
    dwell_ms: int = Field(ge=0, le=86_400_000)
    page_visible: bool


class QualifiedViewResponse(StrictModel):
    qualified: bool
    rewarded: bool
