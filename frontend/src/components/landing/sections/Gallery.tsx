"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { Icon } from "@/components/landing/icons";
import { GALLERY, accentMap } from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

export function Gallery() {
  return (
    <section id="exemplos" className="relative scroll-mt-20 py-20 sm:py-24">
      <Container>
        <SectionHeading
          eyebrow="Galeria de exemplos"
          eyebrowIcon="film"
          accent="mint"
          title="Veja nichos e estilos que você pode criar."
          description="Cada exemplo mostra um tema, um nicho e um estilo de legenda. São demos ilustrativas — a geração real acontece na sua conta."
        />

        <div className="mt-6 flex items-center gap-2 rounded-xl border border-amber-400/20 bg-amber-400/[0.06] px-4 py-3 text-[13px] text-mist">
          <Icon name="shield" className="h-4 w-4 shrink-0 text-amber-300" />
          <span>
            <strong className="text-cloud">Exemplos ilustrativos.</strong> As imagens são de stock e
            representam nichos e formatos possíveis — não são vídeos reais gerados na plataforma.
          </span>
        </div>

        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {GALLERY.map((g, i) => {
            const a = accentMap[g.accent];
            return (
              <Reveal key={g.title} delay={(i % 4) * 70}>
                <article className="group relative overflow-hidden rounded-2xl border border-white/8 bg-panel">
                  <div className="relative aspect-[9/16] overflow-hidden">
                    <img
                      src={g.img}
                      alt={g.alt}
                      loading="lazy"
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                    <div className="absolute inset-0 bg-gradient-to-b from-ink/45 via-transparent to-ink/90" />

                    <div className="absolute inset-x-0 top-0 flex items-center justify-between p-2.5">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full bg-ink/60 px-2 py-1 font-mono text-[9px] uppercase tracking-wide text-cloud backdrop-blur-sm",
                          a.text
                        )}
                      >
                        <span className={cn("h-1.5 w-1.5 rounded-full", a.dot)} />
                        {g.niche}
                      </span>
                      <span className="rounded-full bg-ink/60 px-2 py-1 font-mono text-[9px] text-mist backdrop-blur-sm">
                        {g.duration}
                      </span>
                    </div>

                    <div className="absolute inset-x-0 bottom-0 p-3">
                      <p className="font-display text-sm font-bold uppercase leading-tight text-cloud drop-shadow-[0_2px_8px_rgba(0,0,0,0.7)]">
                        {g.title}
                      </p>
                      <p className="mt-1 flex items-center gap-1 text-[10px] text-mist">
                        <Icon name="mic" className="h-3 w-3" />
                        {g.voice}
                      </p>
                    </div>

                    <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded-full border border-white/15 bg-ink/60 px-2 py-1 font-mono text-[8px] text-cloud opacity-0 backdrop-blur-sm transition-opacity duration-300 group-hover:opacity-100">
                      ILUSTRATIVO
                    </span>
                  </div>
                </article>
              </Reveal>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
