"""Credit pricing helpers for generation workflows."""

from app.credits import CREDIT_TARIFFS
from app.templates import get_template


def get_voice_credit_cost(voice_provider: str) -> int:
    costs = {
        "edge": int(CREDIT_TARIFFS.standard_voice),
        "elevenlabs": int(CREDIT_TARIFFS.dialogue),
        "custom": int(CREDIT_TARIFFS.standard_voice),
    }
    return costs.get(voice_provider, int(CREDIT_TARIFFS.standard_voice))


def get_generation_credit_cost(template_id: str, voice_provider: str) -> int:
    """Return the upfront credit cost for a generation request.

    AI-image templates have real per-video API cost, so they use a floor price
    independent of the narration provider.
    """
    voice_cost = get_voice_credit_cost(voice_provider)
    template = get_template(template_id)
    if template.media.source == "ai_video":
        return max(voice_cost, int(CREDIT_TARIFFS.ai_video))
    if template.media.source == "ai_image":
        return max(voice_cost, int(CREDIT_TARIFFS.ai_image))
    return voice_cost
