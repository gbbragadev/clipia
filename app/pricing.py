"""Credit pricing helpers for generation workflows."""

from app.config import settings
from app.templates import get_template


def get_voice_credit_cost(voice_provider: str) -> int:
    costs = {
        "edge": settings.CREDIT_COST_EDGE,
        "elevenlabs": settings.CREDIT_COST_ELEVENLABS,
        "custom": settings.CREDIT_COST_CUSTOM_AUDIO,
    }
    return costs.get(voice_provider, settings.CREDIT_COST_EDGE)


def get_generation_credit_cost(template_id: str, voice_provider: str) -> int:
    """Return the upfront credit cost for a generation request.

    AI-image templates have real per-video API cost, so they use a floor price
    independent of the narration provider.
    """
    voice_cost = get_voice_credit_cost(voice_provider)
    template = get_template(template_id)
    if template.media.source == "ai_image":
        return max(voice_cost, settings.CREDIT_COST_AI_IMAGE)
    return voice_cost
