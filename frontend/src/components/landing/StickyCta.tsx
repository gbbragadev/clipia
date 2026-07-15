"use client";
import { useScrolledPast } from "@/components/landing/lib/motion";
import { Button } from "@/components/landing/ui/Button";
import { useAb } from "@/components/landing/lib/ab";
import { cn } from "@/components/landing/utils/cn";

export function StickyCta() {
  const past = useScrolledPast("hero");
  const ab = useAb();

  return (
    <div
      role="region"
      aria-label="Ações rápidas"
      data-testid="sticky-cta"
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 lg:hidden",
        "transition-all duration-300",
        past ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-full opacity-0"
      )}
    >
      <div className="border-t border-white/10 bg-ink/90 px-3 py-3 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-2.5">
          <Button href="#preco" variant="secondary" size="md" className="min-h-11 flex-1 px-3">
            Preços
          </Button>
          <Button
            href={ab.signup("sticky")}
            size="md"
            iconRight="arrowRight"
            className="min-h-11 flex-1 px-3"
          >
            Começar
          </Button>
        </div>
      </div>
    </div>
  );
}
