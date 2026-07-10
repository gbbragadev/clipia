"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Highlight } from "@/components/landing/ui/Highlight";
import { Reveal } from "@/components/landing/Reveal";
import { NICHES, accentMap } from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

/** Grid de nichos → páginas SEO reais (/criar/[nicho]) com galerias de vídeos. */
export function NichesGrid() {
  return (
    <section id="nichos" className="relative scroll-mt-20 py-20 sm:py-24">
      <Container>
        <SectionHeading
          eyebrow="Nichos prontos"
          eyebrowIcon="layers"
          accent="azure"
          align="center"
          title={<Highlight text="Escolha um nicho e veja *exemplos reais*." />}
          description="Cada página tem vídeos criados na plataforma para aquele formato."
        />

        <div className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {NICHES.map((n, i) => {
            const a = accentMap[n.accent];
            return (
              <Reveal key={n.id} delay={(i % 4) * 70}>
                <a
                  href={n.href}
                  className="group flex h-full flex-col rounded-2xl border border-white/8 bg-panel/60 p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-white/20 hover:bg-panel"
                >
                  <span className="text-3xl" aria-hidden>
                    {n.emoji}
                  </span>
                  <span className="mt-3 font-semibold text-cloud">{n.label}</span>
                  <span className="mt-1 text-[13px] text-mist">{n.desc}</span>
                  <span className={cn("mt-4 font-mono text-[11px] uppercase tracking-wide opacity-0 transition-opacity duration-200 group-hover:opacity-100", a.text)}>
                    ver exemplos →
                  </span>
                </a>
              </Reveal>
            );
          })}

          <Reveal delay={280}>
            <a
              href="/exemplos"
              className="group flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-transparent p-5 text-center transition-all duration-200 hover:-translate-y-0.5 hover:border-coral/40 hover:bg-panel/40"
            >
              <span className="font-semibold text-cloud">Todos os exemplos</span>
              <span className="mt-1 text-[13px] text-mist">galeria completa</span>
              <span className="mt-4 font-mono text-[11px] uppercase tracking-wide text-coral opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                abrir galeria →
              </span>
            </a>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
