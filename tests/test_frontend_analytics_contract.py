from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_frontend_uses_only_flagged_first_party_analytics_without_client_pii():
    analytics = _read("frontend/src/lib/analytics.ts")
    tracking = _read("frontend/src/components/TrackingScripts.tsx")

    assert 'process.env.NEXT_PUBLIC_ANALYTICS_ENABLED === "true"' in analytics
    assert 'fetch("/api/v1/analytics/events"' in analytics
    assert "sessionStorage" in analytics
    assert 'credentials: "include"' in analytics
    assert "buildAuthHeaders" in analytics
    assert "user_id" not in analytics
    assert "User-Agent" not in analytics
    assert "navigator.userAgent" not in analytics
    assert '"email":' not in analytics.lower()
    assert ".email" not in analytics.lower()
    assert 'from "next/script"' not in tracking
    assert "NEXT_PUBLIC_GA_ID" not in tracking
    assert "NEXT_PUBLIC_META_PIXEL_ID" not in tracking
    assert "googletagmanager" not in tracking
    assert "connect.facebook.net" not in tracking


def test_frontend_instruments_requested_client_funnel_surfaces():
    files = "\n".join(
        _read(path)
        for path in (
            "frontend/src/components/TrackingScripts.tsx",
            "frontend/src/components/ShowcaseSection.tsx",
            "frontend/src/components/dashboard/ReferralCard.tsx",
            "frontend/src/components/ui/FeedbackWidget.tsx",
            "frontend/src/app/dashboard/credits/page.tsx",
        )
    )
    for event_name in (
        "landing_viewed",
        "hero_cta_clicked",
        "example_played",
        "example_completed",
        "pricing_viewed",
        "pricing_package_selected",
        "support_opened",
        "signup_started",
        "onboarding_step_viewed",
        "editor_opened",
        "referral_shared",
        "feedback_submitted",
    ):
        assert event_name in files


def test_admin_ui_exposes_full_funnel_cohorts_and_baseline_gate():
    admin_page = _read("frontend/src/app/dashboard/admin/page.tsx")

    for label in (
        "Visitas",
        "Cliques no CTA",
        "Cadastrados",
        "Verificados",
        "Primeira geracao",
        "Exportaram",
        "Iniciaram checkout",
        "Pagantes",
        "Segundo video",
    ):
        assert label in admin_page
    assert "onboarding_gate_ready" in admin_page
    assert "cohorts.weekly" in admin_page
    assert "cohorts.source" in admin_page
    assert "cohorts.niche" in admin_page
    assert "cohorts.device" in admin_page
