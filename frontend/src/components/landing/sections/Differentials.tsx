"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { Icon, type IconName } from "@/components/landing/icons";
import { DIFFERENTIALS } from "@/components/landing/lib/data";

const CREDIT_FACTS = [
  { icon: "gift", title: "2 créditos grátis", text: "Ao confirmar o e-mail do cadastro." },
  { icon: "card", title: "Pacotes desde R$19,90", text: "Compre mais créditos quando precisar." },
  { icon: "mic", title: "Custo por voz, não por duração", text: "Padrão = 1 crédito · Premium = 2 créditos." },
] as const;

export function Differentials() {
  return (
    <section id="diferenciais" className="relative scroll-mt-20 py-20 sm:py-24">
      <Container>
        <SectionHeading
          eyebrow="Diferenciais"
          eyebrowIcon="bolt"
          accent="azure"
          title="Feito para quem cria no celular."
          description="Pensado para ser direto, honesto e acessível — do navegador ao arquivo final, no desktop ou no celular."
        />

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {DIFFERENTIALS.map((d, i) => (
            <Reveal key={d.title} delay={(i % 3) * 80}>
              <div className="flex h-full items-start gap-3 rounded-2xl border border-white/8 bg-panel/70 p-5 transition-colors hover:border-white/15">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-mint">
                  <Icon name={d.icon as IconName} className="h-5 w-5" />
                </span>
                <div>
                  <h3 className="text-base font-semibold text-cloud">{d.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-mist">{d.text}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>

        {/* credits transparency */}
        <Reveal delay={120} className="mt-4">
          <div className="overflow-hidden rounded-2xl border border-coral/25 bg-gradient-to-br from-coral/[0.1] via-panel to-panel p-6 sm:p-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-md">
                <span className="inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-coral">
                  <Icon name="card" className="h-4 w-4" />
                  Transparência de créditos
                </span>
                <h3 className="mt-3 text-2xl font-bold text-cloud">
                  Você sabe exatamente o que paga.
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-mist">
                  Comece grátis e pague só pelo que usar. O custo depende do tipo de voz — nunca da
                  duração do vídeo.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3 lg:max-w-xl lg:flex-1">
                {CREDIT_FACTS.map((f) => (
                  <div
                    key={f.title}
                    className="rounded-xl border border-white/10 bg-ink/40 p-4"
                  >
                    <Icon name={f.icon as IconName} className="h-5 w-5 text-coral" />
                    <div className="mt-2 text-sm font-semibold text-cloud">{f.title}</div>
                    <div className="mt-1 text-[12px] leading-snug text-mist">{f.text}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
