"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import {
  consumeOnboardingAnalyticsEntry,
  isAnalyticsNiche,
  trackProductEvent,
} from "@/lib/analytics";
import { parseSelectedPackage } from "@/lib/package-intent";

function referrerDomain(): string | null {
  if (!document.referrer) return null;
  try {
    const hostname = new URL(document.referrer).hostname.toLowerCase();
    return hostname.includes(".") && hostname !== window.location.hostname.toLowerCase() ? hostname : null;
  } catch {
    return null;
  }
}

function sourcePage(): "landing" | "niche" | "blog" | "examples" | "credits" {
  try {
    const path = document.referrer ? new URL(document.referrer).pathname : "";
    if (path.startsWith("/criar/")) return "niche";
    if (path.startsWith("/blog")) return "blog";
    if (path.startsWith("/exemplos")) return "examples";
    if (path.startsWith("/dashboard/credits")) return "credits";
  } catch {
    // Direct and invalid referrers are attributed to the landing source bucket.
  }
  return "landing";
}

function ctaPlacement(value: string | null): "hero" | "nav" | "final" {
  if (value === "hero") return "hero";
  if (value?.startsWith("nav")) return "nav";
  return "final";
}

export default function TrackingScripts() {
  const pathname = usePathname();

  useEffect(() => {
    const current = new URL(window.location.href);
    if (pathname === "/") {
      const campaign = current.searchParams.get("utm_campaign") ?? "";
      const niche = campaign.startsWith("nicho-") ? campaign.slice("nicho-".length) : "";
      trackProductEvent(
        "landing_viewed",
        {
          landing_variant: "control",
          niche: isAnalyticsNiche(niche) ? niche : null,
          referrer_domain: referrerDomain(),
        },
        { once: "landing-viewed", page: "landing" },
      );
    }
    if (pathname.startsWith("/auth/register")) {
      const selectedPackage = parseSelectedPackage(current.searchParams.get("selected_package"));
      trackProductEvent(
        "signup_started",
        { selected_package: selectedPackage, source_page: sourcePage() },
        { once: `signup-started:${selectedPackage ?? "none"}`, page: "auth_register" },
      );
    }
    if (pathname.startsWith("/suporte")) {
      trackProductEvent(
        "support_opened",
        { placement: "app", reason_code: null },
        { once: "support-opened", page: "support" },
      );
    }
    if (pathname.startsWith("/editor/")) {
      const referrer = document.referrer;
      const entry = referrer.includes("/v/") ? "viewer" : referrer.includes("/dashboard") ? "dashboard" : "generation_complete";
      trackProductEvent("editor_opened", { entry }, { once: `editor-opened:${pathname}`, page: "editor" });
    }
    if (pathname === "/dashboard") {
      const entry = consumeOnboardingAnalyticsEntry();
      if (entry) {
        trackProductEvent(
          "onboarding_step_viewed",
          { step: "first_video", entry },
          { once: `onboarding-first-video:${entry}`, page: "dashboard" },
        );
      }
    }
  }, [pathname]);

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (!(event.target instanceof Element)) return;
      const anchor = event.target.closest<HTMLAnchorElement>("a[href]");
      if (!anchor) return;
      const url = new URL(anchor.href, window.location.href);

      if (url.pathname === "/auth/register" && !pathname.startsWith("/auth/")) {
        const selectedPackage = parseSelectedPackage(url.searchParams.get("selected_package"));
        const placement = ctaPlacement(url.searchParams.get("placement"));
        trackProductEvent(
          "hero_cta_clicked",
          { placement, cta_variant: "control", selected_package: selectedPackage },
          { once: `cta:${placement}:${selectedPackage ?? "none"}`, page: pathname === "/" ? "landing" : undefined },
        );
        if (selectedPackage) {
          trackProductEvent(
            "pricing_package_selected",
            { package: selectedPackage, placement: pathname === "/dashboard/credits" ? "credits" : "landing" },
            { once: `package-selected:${selectedPackage}:${pathname}` },
          );
        }
      }

      if (url.pathname === "/suporte" || url.protocol === "mailto:") {
        const placement = anchor.closest("footer") ? "footer" : anchor.closest("details") ? "faq" : "app";
        trackProductEvent(
          "support_opened",
          { placement, reason_code: null },
          { once: "support-opened", page: pathname === "/" ? "landing" : undefined },
        );
      }
    }

    document.addEventListener("click", handleClick, { capture: true });
    const pricing = document.getElementById("preco");
    const observer = pricing
      ? new IntersectionObserver(
          ([entry]) => {
            if (entry.isIntersecting) {
              trackProductEvent(
                "pricing_viewed",
                { placement: pathname === "/dashboard/credits" ? "credits" : "landing", pricing_variant: "control" },
                { once: `pricing-viewed:${pathname}` },
              );
              observer?.disconnect();
            }
          },
          { threshold: 0.35 },
        )
      : null;
    if (pricing && observer) observer.observe(pricing);

    return () => {
      document.removeEventListener("click", handleClick, { capture: true });
      observer?.disconnect();
    };
  }, [pathname]);

  return null;
}
