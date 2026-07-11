"use client";
import { Icon, type IconName } from "@/components/landing/icons";
import { FACTS } from "@/components/landing/lib/data";

const ACCENTS = ["text-coral", "text-azure", "text-mint"] as const;

/** Faixa de fatos verificáveis do produto — marquee contínuo, pausa no hover. */
export function FactsBar() {
  const row = [...FACTS, ...FACTS];
  return (
    <section aria-label="Especificações do produto" className="border-y border-white/8 bg-ink-2/70 py-4">
      <div className="relative overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_10%,#000_90%,transparent)]">
        <div className="anim-marquee flex w-max items-center gap-3">
          {row.map((f, i) => (
            <span
              key={i}
              aria-hidden={i >= FACTS.length}
              className="flex shrink-0 items-center gap-2 rounded-full border border-white/8 bg-panel/60 px-4 py-2 text-sm text-mist"
            >
              <Icon name={f.icon as IconName} className={`h-4 w-4 ${ACCENTS[i % ACCENTS.length]}`} />
              {f.text}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
