"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { Icon, type IconName } from "@/components/landing/icons";
import { ANATOMY, SPECS, accentMap } from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

const LAYER_ACCENTS = ["coral", "azure", "mint", "coral", "mint"] as const;

export function ProductProof() {
  return (
    <section className="relative py-20 sm:py-24">
      <Container>
        <SectionHeading
          eyebrow="Prova de produto"
          eyebrowIcon="layers"
          accent="mint"
          title="O que está dentro de cada vídeo."
          description="Sem promessas vazias: isto é, objetivamente, o que a plataforma entrega em cada criação."
        />

        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          {/* anatomy */}
          <Reveal className="rounded-2xl border border-white/8 bg-panel/70 p-6 sm:p-8">
            <h3 className="flex items-center gap-2 text-lg font-semibold text-cloud">
              <Icon name="film" className="h-5 w-5 text-coral" />
              Anatomia de um vídeo vertical
            </h3>
            <p className="mt-1 text-sm text-mist">
              Um vídeo da ClipIA é a combinação destas camadas, já sincronizadas.
            </p>
            <div className="mt-5 space-y-2.5">
              {ANATOMY.map((l, i) => {
                const a = accentMap[LAYER_ACCENTS[i % LAYER_ACCENTS.length]];
                return (
                  <div
                    key={l.label}
                    className="flex items-center gap-3 rounded-xl border border-white/8 bg-ink/40 p-3"
                    style={{ marginLeft: `${i * 8}px` }}
                  >
                    <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-lg border", a.soft, a.border, a.text)}>
                      <Icon name={l.icon as IconName} className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-cloud">{l.label}</div>
                      <div className="text-[12px] text-mist">{l.desc}</div>
                    </div>
                    <span className="ml-auto font-mono text-[10px] text-mist-2">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </div>
                );
              })}
            </div>
          </Reveal>

          {/* specs */}
          <Reveal delay={100} className="rounded-2xl border border-white/8 bg-panel/70 p-6 sm:p-8">
            <h3 className="flex items-center gap-2 text-lg font-semibold text-cloud">
              <Icon name="shield" className="h-5 w-5 text-mint" />
              Especificações
            </h3>
            <p className="mt-1 text-sm text-mist">O formato e os recursos de cada entrega.</p>
            <dl className="mt-5 divide-y divide-white/8">
              {SPECS.map((s) => (
                <div key={s.k} className="flex flex-col gap-0.5 py-3 sm:flex-row sm:gap-4">
                  <dt className="w-44 shrink-0 font-mono text-[11px] uppercase tracking-wider text-mist-2">
                    {s.k}
                  </dt>
                  <dd className="text-sm text-cloud">{s.v}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-5 flex items-start gap-2 rounded-xl border border-white/8 bg-ink/40 p-4 text-[13px] text-mist">
              <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-mint" />
              <span>
                Sem garantias de viralizar ou de engajamento. A ferramenta acelera a criação; o
                resultado depende do tema, do nicho e dos ajustes no editor.
              </span>
            </div>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
