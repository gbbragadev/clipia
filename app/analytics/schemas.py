from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Niche = Literal["curiosidades", "religioso", "motivacional", "financas", "historias", "humor", "drama"]
Package = Literal["starter", "popular", "professional"]
Page = Literal[
    "landing",
    "examples",
    "niche",
    "blog",
    "support",
    "auth_register",
    "credits",
    "dashboard",
    "editor",
    "viewer",
]
DeviceClass = Literal["desktop", "mobile", "tablet", "unknown"]
ExampleId = Literal[
    "o-fato-historico-que-quase-ninguem-conhece",
    "3-formas-de-economizar-sem-perceber",
    "a-disciplina-vence-a-motivacao",
    "mensagem-de-fe-para-o-seu-dia",
    "segredos-do-oceano-profundo",
    "ocean",
    "ia",
    "cerebro",
]
CampaignToken = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=100, pattern=r"^[a-z0-9._-]+$"),
]
ReferrerDomain = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=1,
        max_length=100,
        pattern=r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    ),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LandingViewedProperties(StrictModel):
    landing_variant: Literal["control"]
    niche: Niche | None = None
    referrer_domain: ReferrerDomain | None = None


class HeroCtaClickedProperties(StrictModel):
    placement: Literal["hero", "nav", "final"]
    cta_variant: Literal["control"]
    selected_package: Package | None = None


class ExamplePlayedProperties(StrictModel):
    example_id: ExampleId
    niche: Niche
    placement: Literal["hero", "landing", "examples", "niche", "viewer"]


class ExampleCompletedProperties(StrictModel):
    example_id: ExampleId
    completion_bucket: Literal[25, 50, 75, 100]


class PricingViewedProperties(StrictModel):
    placement: Literal["landing", "credits"]
    pricing_variant: Literal["control"]


class PricingPackageSelectedProperties(StrictModel):
    package: Package
    placement: Literal["landing", "credits"]


class SupportOpenedProperties(StrictModel):
    placement: Literal["footer", "faq", "app", "error"]
    reason_code: Literal["payment", "generation", "export", "auth", "other"] | None = None


class SignupStartedProperties(StrictModel):
    selected_package: Package | None = None
    source_page: Literal["landing", "niche", "blog", "examples", "credits"]


class CreditsViewedProperties(StrictModel):
    balance_bucket: Literal["zero", "low", "medium", "high"]
    placement: Literal["dashboard", "editor", "generation", "credits"]


class CreditsLowProperties(StrictModel):
    balance_bucket: Literal["zero", "low"]
    required_bucket: Literal["standard", "dialogue", "refinement", "ai_image", "ai_video"]
    placement: Literal["generation", "editor"]


class UserReturnedProperties(StrictModel):
    entry: Literal["email", "direct", "dashboard"]
    days_since_last_value_bucket: Literal["same_day", "1_7", "8_30", "31_90", "over_90"]


class ReferralSharedProperties(StrictModel):
    channel: Literal["whatsapp", "copy_link", "other"]
    placement: Literal["after_export", "dashboard", "credits"]


class FeedbackSubmittedProperties(StrictModel):
    score: Literal[1, 2, 3, 4, 5]
    context: Literal["first_export", "general"]


class OnboardingStepViewedProperties(StrictModel):
    step: Literal["package_confirmation", "goal_niche", "first_video", "progress", "result", "feedback"]
    entry: Literal["direct", "package", "niche"]


class EditorOpenedProperties(StrictModel):
    entry: Literal["generation_complete", "dashboard", "viewer"]


class ClientEventBase(StrictModel):
    event_id: UUID4
    event_name: str
    schema_version: Literal[1]
    occurred_at: datetime
    anonymous_session_id: UUID4 | None = None
    page: Page
    device_class: DeviceClass
    utm_source: CampaignToken | None = None
    utm_medium: CampaignToken | None = None
    utm_campaign: CampaignToken | None = None
    utm_content: CampaignToken | None = None
    utm_term: CampaignToken | None = None

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        value = value.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if value > now + timedelta(minutes=5) or value < now - timedelta(hours=24):
            raise ValueError("occurred_at outside the accepted window")
        return value


class LandingViewedEvent(ClientEventBase):
    event_name: Literal["landing_viewed"]
    properties: LandingViewedProperties


class HeroCtaClickedEvent(ClientEventBase):
    event_name: Literal["hero_cta_clicked"]
    properties: HeroCtaClickedProperties


class ExamplePlayedEvent(ClientEventBase):
    event_name: Literal["example_played"]
    properties: ExamplePlayedProperties


class ExampleCompletedEvent(ClientEventBase):
    event_name: Literal["example_completed"]
    properties: ExampleCompletedProperties


class PricingViewedEvent(ClientEventBase):
    event_name: Literal["pricing_viewed"]
    properties: PricingViewedProperties


class PricingPackageSelectedEvent(ClientEventBase):
    event_name: Literal["pricing_package_selected"]
    properties: PricingPackageSelectedProperties


class SupportOpenedEvent(ClientEventBase):
    event_name: Literal["support_opened"]
    properties: SupportOpenedProperties


class SignupStartedEvent(ClientEventBase):
    event_name: Literal["signup_started"]
    properties: SignupStartedProperties


class CreditsViewedEvent(ClientEventBase):
    event_name: Literal["credits_viewed"]
    properties: CreditsViewedProperties


class CreditsLowEvent(ClientEventBase):
    event_name: Literal["credits_low"]
    properties: CreditsLowProperties


class UserReturnedEvent(ClientEventBase):
    event_name: Literal["user_returned"]
    properties: UserReturnedProperties


class ReferralSharedEvent(ClientEventBase):
    event_name: Literal["referral_shared"]
    properties: ReferralSharedProperties


class FeedbackSubmittedEvent(ClientEventBase):
    event_name: Literal["feedback_submitted"]
    properties: FeedbackSubmittedProperties


class OnboardingStepViewedEvent(ClientEventBase):
    event_name: Literal["onboarding_step_viewed"]
    properties: OnboardingStepViewedProperties


class EditorOpenedEvent(ClientEventBase):
    event_name: Literal["editor_opened"]
    properties: EditorOpenedProperties


ClientEvent = Annotated[
    LandingViewedEvent
    | HeroCtaClickedEvent
    | ExamplePlayedEvent
    | ExampleCompletedEvent
    | PricingViewedEvent
    | PricingPackageSelectedEvent
    | SupportOpenedEvent
    | SignupStartedEvent
    | CreditsViewedEvent
    | CreditsLowEvent
    | UserReturnedEvent
    | ReferralSharedEvent
    | FeedbackSubmittedEvent
    | OnboardingStepViewedEvent
    | EditorOpenedEvent,
    Field(discriminator="event_name"),
]


class UserRegisteredProperties(StrictModel):
    selected_package: Package | None = None
    niche: Niche | None = None


class EmailVerifiedProperties(StrictModel):
    welcome_credits: int = Field(ge=0, le=100)


class GenerationRequestedProperties(StrictModel):
    operation_kind: Literal["generation", "rerender"]
    credit_cost: int = Field(ge=0, le=100)
    generation_ordinal: Literal["first", "second", "repeat"]


class GenerationTerminalProperties(StrictModel):
    operation_kind: Literal["generation", "rerender"]
    generation_ordinal: Literal["first", "second", "repeat"]


class GenerationFailedProperties(GenerationTerminalProperties):
    reason_code: Literal["pipeline", "provider", "cancelled", "persistence", "unknown"]


class VideoExportedProperties(StrictModel):
    export_ordinal: Literal["first", "repeat"]


class CheckoutProperties(StrictModel):
    provider: Literal["mercadopago", "stripe"]
    package: Package
    total_credits: int = Field(gt=0, le=10_000)


class CreditBalanceChangedProperties(StrictModel):
    reason: Literal[
        "welcome",
        "purchase",
        "refund",
        "generation_debit",
        "generation_refund",
        "rerender_debit",
        "rerender_refund",
        "admin",
        "referral",
        "campaign_signup",
        "referral_activation",
        "social_share",
        "other",
    ]
    delta: int = Field(ge=-10_000, le=10_000)

    @field_validator("delta")
    @classmethod
    def reject_zero_delta(cls, value: int) -> int:
        if value == 0:
            raise ValueError("delta must be non-zero")
        return value


class SecondGenerationRequestedProperties(StrictModel):
    credit_cost: int = Field(ge=0, le=100)


class SharePageProperties(StrictModel):
    share_id: UUID4
    job_id: UUID4


class SocialShareRewardedProperties(SharePageProperties):
    credits: Literal[2]


ServerEventName = Literal[
    "user_registered",
    "email_verified",
    "generation_requested",
    "generation_completed",
    "generation_failed",
    "video_exported",
    "checkout_started",
    "payment_completed",
    "credit_balance_changed",
    "second_generation_requested",
    "share_page_published",
    "share_page_visited",
    "social_share_rewarded",
]

SERVER_EVENT_PROPERTY_MODELS: dict[str, type[StrictModel]] = {
    "user_registered": UserRegisteredProperties,
    "email_verified": EmailVerifiedProperties,
    "generation_requested": GenerationRequestedProperties,
    "generation_completed": GenerationTerminalProperties,
    "generation_failed": GenerationFailedProperties,
    "video_exported": VideoExportedProperties,
    "checkout_started": CheckoutProperties,
    "payment_completed": CheckoutProperties,
    "credit_balance_changed": CreditBalanceChangedProperties,
    "second_generation_requested": SecondGenerationRequestedProperties,
    "share_page_published": SharePageProperties,
    "share_page_visited": SharePageProperties,
    "social_share_rewarded": SocialShareRewardedProperties,
}


class AnalyticsBatch(StrictModel):
    events: list[ClientEvent] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def reject_duplicate_ids(self):
        ids = [event.event_id for event in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("event_id duplicated inside batch")
        return self


class AnalyticsIngestResponse(StrictModel):
    accepted: int
    duplicates: int
    enabled: bool
