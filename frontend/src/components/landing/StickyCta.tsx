"use client";
import { useScrolledPast } from "@/components/landing/lib/motion";
import { Button } from "@/components/landing/ui/Button";
import { CTA_LABEL, signupUrl } from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

export function StickyCta() {
  const past = useScrolledPast("hero");

  return (
    <div
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 lg:hidden",
        "transition-all duration-300",
        past ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-full opacity-0"
      )}
    >
      <div className="border-t border-white/10 bg-ink/90 px-4 py-3 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-3">
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm font-semibold text-cloud">{CTA_LABEL}</p>
            <p className="truncate text-[11px] text-mist">Sem cartão · narração em pt-BR</p>
          </div>
          <Button href={signupUrl("sticky")} size="md" iconRight="arrowRight" className="shrink-0">
            Começar
          </Button>
        </div>
      </div>
    </div>
  );
}
