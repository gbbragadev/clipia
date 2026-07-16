from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_creator_campaign_is_the_only_registration_surface_that_promises_twenty_credits():
    register_page = _read("frontend/src/app/auth/register/page.tsx")
    campaign_page = _read("frontend/src/app/oferta/criadores/page.tsx")

    assert "FREE_CLAIM" in register_page
    assert "20 créditos" not in register_page
    assert "20 créditos" in campaign_page
    assert "2 créditos de boas-vindas + 18 créditos da oferta" in campaign_page
    assert (
        "/auth/register?offer=creator20_v1&utm_source=meta&utm_medium=paid_social&utm_campaign=clipia_creator20_pilot"
    ) in campaign_page
    assert "cronômetro" not in campaign_page.lower()
    assert "últimas vagas" not in campaign_page.lower()


def test_registration_propagates_offer_and_keeps_measurement_consent_optional_and_separate():
    attribution = _read("frontend/src/hooks/useUTM.ts")
    auth = _read("frontend/src/lib/auth.ts")
    context = _read("frontend/src/contexts/AuthContext.tsx")
    register_page = _read("frontend/src/app/auth/register/page.tsx")

    assert "captureRegistrationAttribution" in attribution
    assert "readRegistrationAttribution" in attribution
    assert "offer_code?: string" in auth
    assert "marketing_measurement_consent?: boolean" in auth
    assert "marketingMeasurementConsent" in register_page
    assert "useState(false)" in register_page
    assert "Medição opcional" in register_page
    assert "marketingMeasurementConsent" in context
    assert "marketing_measurement_consent: marketingMeasurementConsent" in context
    assert context.index("const res = await authRegister") < context.index("clearStoredUTM();")


def test_public_share_clients_and_route_preserve_showcase_then_resolve_opt_in_tokens():
    clients = _read("frontend/src/lib/public-shares.ts")
    page = _read("frontend/src/app/v/[id]/page.tsx")
    assert "createPublicShare" in clients
    assert "revokePublicShare" in clients
    assert "getPublicShare" in clients
    assert "VIDEOS.find" in page
    assert "getPublicShare" in page
    assert "generateMetadata" in page
    assert "dynamicParams = false" not in page
    assert "QualifiedViewTracker" in page
    assert "<JsonLd" in page
    assert "dangerouslySetInnerHTML" not in page
    assert (
        "utm_source=public_share&utm_medium=organic_social&utm_campaign=creator20_v1&utm_content=public_video"
    ) in page
    assert "utm_content=${encodeURIComponent(video.id)}" not in page


def test_completed_video_sharing_is_explicit_and_revocable():
    card = _read("frontend/src/components/dashboard/VideoCard.tsx")

    for copy in (
        "Publicar link",
        "Copiar link",
        "Revogar link",
        "Só fica público quando você publicar",
        "createPublicShare",
        "revokePublicShare",
    ):
        assert copy in card


def test_referral_and_legal_copy_match_the_growth_reward_rules():
    referral = _read("frontend/src/components/dashboard/ReferralCard.tsx")
    terms = _read("frontend/src/app/termos/page.tsx")
    privacy = _read("frontend/src/app/privacidade/page.tsx")

    assert "+18 créditos" in referral
    assert "verificar o e-mail e concluir o primeiro vídeo" in referral
    assert "Vocês dois" not in referral
    for copy in ("oferta de campanha", "indicação", "compartilhamento público"):
        assert copy in terms.lower()
    for copy in ("mensuração de marketing", "opcional", "5 segundos", "identificador anônimo"):
        assert copy in privacy.lower()
