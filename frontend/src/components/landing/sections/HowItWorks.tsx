"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { Icon } from "@/components/landing/icons";
import { STEPS, accentMap } from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

function MiniVisual({ index }: { index: number }) {
  if (index === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-ink/50 p-3">
        <div className="font-mono text-[9px] uppercase text-mist-2">Tema</div>
        <div className="mt-1.5 flex items-center gap-1.5 text-xs text-cloud">
          <Icon name="sparkles" className="h-3.5 w-3.5 text-coral" />
          <span>Curiosidades sobre o espaço</span>
          <span className="anim-caret text-coral">▌</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {["Curiosidades", "30s", "Feminina"].map((t) => (
            <span
              key={t}
              className="rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[9px] text-mist"
            >
              {t}
            </span>
          ))}
        </div>
      </div>
    );
  }
  if (index === 1) {
    return (
      <div className="rounded-xl border border-white/10 bg-ink/50 p-3">
        <div className="space-y-1.5">
          {[
            { icon: "edit", label: "Roteiro", c: "text-coral" },
            { icon: "mic", label: "Narração pt-BR", c: "text-azure" },
            { icon: "caption", label: "Legendas", c: "text-mint" },
          ].map((row, i) => (
            <div key={row.label} className="flex items-center gap-2">
              <span className={cn("grid h-6 w-6 place-items-center rounded-md bg-white/[0.05]", row.c)}>
                <Icon name={row.icon as "edit"} className="h-3.5 w-3.5" />
              </span>
              <span className="text-xs text-cloud">{row.label}</span>
              {i === 1 && (
                <span className="ml-auto flex h-3 items-end gap-px">
                  {[3, 6, 4, 7, 5].map((h, k) => (
                    <span
                      key={k}
                      className="anim-equalize w-px rounded-full bg-azure/70"
                      style={{ height: `${h * 3}px`, animationDelay: `${k * 90}ms` }}
                    />
                  ))}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-center justify-between rounded-xl border border-white/10 bg-ink/50 p-3">
      <div className="flex items-center gap-2">
        <div className="relative h-12 w-7 overflow-hidden rounded-md ring-1 ring-white/10">
          <img
            src="https://images.pexels.com/photos/17954395/pexels-photo-17954395.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=300&w=200"
            alt=""
            className="h-full w-full object-cover"
          />
          <span className="absolute bottom-0.5 left-0.5 rounded bg-ink/70 px-1 font-mono text-[7px] text-cloud">
            9:16
          </span>
        </div>
        <div>
          <div className="text-xs font-medium text-cloud">MP4 vertical</div>
          <div className="font-mono text-[9px] text-mist-2">Pronto para publicar</div>
        </div>
      </div>
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-mint/15 text-mint">
        <Icon name="download" className="h-4 w-4" />
      </span>
    </div>
  );
}

export function HowItWorks() {
  return (
    <section id="como-funciona" className="relative scroll-mt-20 py-20 sm:py-24">
      <Container>
        <SectionHeading
          eyebrow="Como funciona"
          eyebrowIcon="bolt"
          accent="azure"
          align="center"
          title="Do tema ao vídeo pronto em três passos."
          description="Sem instalação e sem etapas manuais chatas. Você descreve, a IA monta e você só revisa."
        />

        <div className="relative mt-14 grid gap-6 lg:grid-cols-3">
          {/* connecting line (desktop) */}
          <div
            aria-hidden
            className="absolute left-0 right-0 top-[3.25rem] hidden h-px bg-gradient-to-r from-coral/40 via-azure/40 to-mint/40 lg:block"
          />
          {STEPS.map((s, i) => {
            const a = accentMap[s.accent];
            return (
              <Reveal key={s.n} delay={i * 110} className="relative">
                <div className="flex h-full flex-col rounded-2xl border border-white/8 bg-panel/70 p-6">
                  <div className="flex items-center justify-between">
                    <span
                      className={cn(
                        "relative z-10 grid h-10 w-10 place-items-center rounded-xl border font-mono text-sm font-semibold",
                        a.soft,
                        a.border,
                        a.text
                      )}
                    >
                      {s.n}
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-wider text-mist-2">
                      Passo {i + 1}
                    </span>
                  </div>
                  <h3 className="mt-5 text-xl font-semibold text-cloud">{s.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-mist">{s.text}</p>
                  <div className="mt-5">
                    <MiniVisual index={i} />
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
