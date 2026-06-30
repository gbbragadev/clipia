"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { Icon, type IconName } from "@/components/landing/icons";
import { VALUE_PROPS, accentMap } from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

export function ValueProps() {
  return (
    <section className="relative py-20 sm:py-24">
      <Container>
        <SectionHeading
          eyebrow="Proposta de valor"
          eyebrowIcon="sparkles"
          accent="coral"
          title={
            <>
              Tudo o que um vídeo vertical precisa,{" "}
              <span className="text-mist">em um só lugar.</span>
            </>
          }
          description="Da ideia ao arquivo pronto: a ClipIA cuida do roteiro, da narração, das legendas e da edição para você publicar mais rápido."
        />

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {VALUE_PROPS.map((p, i) => {
            const a = accentMap[p.accent];
            return (
              <Reveal key={p.title} delay={i * 80}>
                <article className="group h-full rounded-2xl border border-white/8 bg-panel/70 p-6 transition-all duration-300 hover:-translate-y-1 hover:border-white/15 hover:bg-panel">
                  <span
                    className={cn(
                      "grid h-12 w-12 place-items-center rounded-xl border",
                      a.soft,
                      a.border,
                      a.text
                    )}
                  >
                    <Icon name={p.icon as IconName} className="h-6 w-6" />
                  </span>
                  <h3 className="mt-5 text-lg font-semibold text-cloud">{p.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-mist">{p.text}</p>
                </article>
              </Reveal>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
