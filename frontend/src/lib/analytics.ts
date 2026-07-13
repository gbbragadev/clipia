"use client";

import { getStoredAttribution } from "@/hooks/useUTM";
import type { SelectedPackage } from "@/lib/package-intent";
import { buildAuthHeaders } from "@/lib/session";

export const ANALYTICS_NICHES = [
  "curiosidades",
  "religioso",
  "motivacional",
  "financas",
  "historias",
  "humor",
  "drama",
] as const;
export type AnalyticsNiche = (typeof ANALYTICS_NICHES)[number];

export const ANALYTICS_EXAMPLE_IDS = [
  "o-fato-historico-que-quase-ninguem-conhece",
  "3-formas-de-economizar-sem-perceber",
  "a-disciplina-vence-a-motivacao",
  "mensagem-de-fe-para-o-seu-dia",
  "segredos-do-oceano-profundo",
  "ocean",
  "ia",
  "cerebro",
] as const;
export type AnalyticsExampleId = (typeof ANALYTICS_EXAMPLE_IDS)[number];

type AnalyticsPage =
  | "landing"
  | "examples"
  | "niche"
  | "blog"
  | "support"
  | "auth_register"
  | "credits"
  | "dashboard"
  | "editor"
  | "viewer";

type EventProperties = {
  landing_viewed: {
    landing_variant: "control";
    niche: AnalyticsNiche | null;
    referrer_domain: string | null;
  };
  hero_cta_clicked: {
    placement: "hero" | "nav" | "final";
    cta_variant: "control";
    selected_package: SelectedPackage | null;
  };
  example_played: {
    example_id: AnalyticsExampleId;
    niche: AnalyticsNiche;
    placement: "hero" | "landing" | "examples" | "niche" | "viewer";
  };
  example_completed: {
    example_id: AnalyticsExampleId;
    completion_bucket: 25 | 50 | 75 | 100;
  };
  pricing_viewed: { placement: "landing" | "credits"; pricing_variant: "control" };
  pricing_package_selected: { package: SelectedPackage; placement: "landing" | "credits" };
  support_opened: {
    placement: "footer" | "faq" | "app" | "error";
    reason_code: "payment" | "generation" | "export" | "auth" | "other" | null;
  };
  signup_started: {
    selected_package: SelectedPackage | null;
    source_page: "landing" | "niche" | "blog" | "examples" | "credits";
  };
  credits_viewed: {
    balance_bucket: "zero" | "low" | "medium" | "high";
    placement: "dashboard" | "editor" | "generation" | "credits";
  };
  credits_low: {
    balance_bucket: "zero" | "low";
    required_bucket: "standard" | "dialogue" | "refinement" | "ai_image" | "ai_video";
    placement: "generation" | "editor";
  };
  user_returned: {
    entry: "email" | "direct" | "dashboard";
    days_since_last_value_bucket: "same_day" | "1_7" | "8_30" | "31_90" | "over_90";
  };
  referral_shared: {
    channel: "whatsapp" | "copy_link" | "other";
    placement: "after_export" | "dashboard" | "credits";
  };
  feedback_submitted: { score: 1 | 2 | 3 | 4 | 5; context: "first_export" | "general" };
  onboarding_step_viewed: {
    step: "package_confirmation" | "goal_niche" | "first_video" | "progress" | "result" | "feedback";
    entry: "direct" | "package" | "niche";
  };
  editor_opened: { entry: "generation_complete" | "dashboard" | "viewer" };
};

export type AnalyticsEventName = keyof EventProperties;
export type OnboardingAnalyticsEntry = EventProperties["onboarding_step_viewed"]["entry"];

const SESSION_KEY = "clipia_analytics_session";
const ONBOARDING_ENTRY_KEY = "clipia_analytics_onboarding_entry";
const ONCE_PREFIX = "clipia_analytics_once:";
const CAMPAIGN_TOKEN = /^[a-z0-9._-]{1,100}$/;
const ANALYTICS_ENABLED = process.env.NEXT_PUBLIC_ANALYTICS_ENABLED === "true";
let volatileSessionId: string | null = null;

function randomId(): string {
  if (typeof crypto === "undefined" || typeof crypto.randomUUID !== "function") {
    throw new Error("Secure browser UUID generation is unavailable");
  }
  return crypto.randomUUID();
}

function anonymousSessionId(): string {
  if (volatileSessionId) return volatileSessionId;
  try {
    const stored = window.sessionStorage.getItem(SESSION_KEY);
    if (stored) return (volatileSessionId = stored);
    volatileSessionId = randomId();
    window.sessionStorage.setItem(SESSION_KEY, volatileSessionId);
    return volatileSessionId;
  } catch {
    return (volatileSessionId = randomId());
  }
}

function campaignToken(value: string | undefined): string | null {
  const normalized = value?.trim().toLowerCase();
  return normalized && CAMPAIGN_TOKEN.test(normalized) ? normalized : null;
}

export function analyticsPage(pathname: string): AnalyticsPage {
  if (pathname === "/") return "landing";
  if (pathname.startsWith("/exemplos")) return "examples";
  if (pathname.startsWith("/criar/")) return "niche";
  if (pathname.startsWith("/blog")) return "blog";
  if (pathname.startsWith("/suporte")) return "support";
  if (pathname.startsWith("/auth/register")) return "auth_register";
  if (pathname.startsWith("/dashboard/credits")) return "credits";
  if (pathname.startsWith("/editor/")) return "editor";
  if (pathname.startsWith("/v/")) return "viewer";
  return "dashboard";
}

function deviceClass(): "desktop" | "mobile" | "tablet" {
  if (window.innerWidth < 768) return "mobile";
  if (window.innerWidth < 1024) return "tablet";
  return "desktop";
}

function claimOnce(key: string | undefined): boolean {
  if (!key) return true;
  try {
    const storageKey = `${ONCE_PREFIX}${key}`;
    if (window.sessionStorage.getItem(storageKey)) return false;
    window.sessionStorage.setItem(storageKey, "1");
    return true;
  } catch {
    return true;
  }
}

export function isAnalyticsNiche(value: string): value is AnalyticsNiche {
  return (ANALYTICS_NICHES as readonly string[]).includes(value);
}

export function isAnalyticsExampleId(value: string): value is AnalyticsExampleId {
  return (ANALYTICS_EXAMPLE_IDS as readonly string[]).includes(value);
}

export function setOnboardingAnalyticsEntry(entry: OnboardingAnalyticsEntry): void {
  try {
    window.sessionStorage.setItem(ONBOARDING_ENTRY_KEY, entry);
  } catch {
    // Best-effort analytics cannot block registration.
  }
}

export function consumeOnboardingAnalyticsEntry(): OnboardingAnalyticsEntry | null {
  try {
    const entry = window.sessionStorage.getItem(ONBOARDING_ENTRY_KEY);
    window.sessionStorage.removeItem(ONBOARDING_ENTRY_KEY);
    return entry === "direct" || entry === "package" || entry === "niche" ? entry : null;
  } catch {
    return null;
  }
}

export function trackProductEvent<Name extends AnalyticsEventName>(
  eventName: Name,
  properties: EventProperties[Name],
  options: { once?: string; page?: AnalyticsPage } = {},
): void {
  if (!ANALYTICS_ENABLED || typeof window === "undefined" || !claimOnce(options.once)) return;

  const storedAttribution = getStoredAttribution();
  const currentParams = new URLSearchParams(window.location.search);
  const attribution = {
    utm_source: currentParams.get("utm_source") ?? storedAttribution.utm_source,
    utm_medium: currentParams.get("utm_medium") ?? storedAttribution.utm_medium,
    utm_campaign: currentParams.get("utm_campaign") ?? storedAttribution.utm_campaign,
    utm_content: currentParams.get("utm_content") ?? storedAttribution.utm_content,
    utm_term: currentParams.get("utm_term") ?? storedAttribution.utm_term,
  };
  const event = {
    event_id: randomId(),
    event_name: eventName,
    schema_version: 1,
    occurred_at: new Date().toISOString(),
    anonymous_session_id: anonymousSessionId(),
    page: options.page ?? analyticsPage(window.location.pathname),
    device_class: deviceClass(),
    utm_source: campaignToken(attribution.utm_source),
    utm_medium: campaignToken(attribution.utm_medium),
    utm_campaign: campaignToken(attribution.utm_campaign),
    utm_content: campaignToken(attribution.utm_content),
    utm_term: campaignToken(attribution.utm_term),
    properties,
  };
  const headers = buildAuthHeaders("POST", { "Content-Type": "application/json" });
  void fetch("/api/v1/analytics/events", {
    method: "POST",
    headers,
    credentials: "include",
    keepalive: true,
    body: JSON.stringify({ events: [event] }),
  }).catch(() => undefined);
}
