"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { Icon } from "@/components/landing/icons";
import { FAQ_ITEMS, SITE } from "@/components/landing/lib/data";
import { Button } from "@/components/landing/ui/Button";

export function FAQ() {
  return (
    <section id="faq" className="relative scroll-mt-20 py-20 sm:py-24">
      <Container>
        <SectionHeading
          eyebrow="Dúvidas frequentes"
          eyebrowIcon="caption"
          accent="coral"
          align="center"
          title="Perguntas e respostas diretas."
        />

        <div className="mx-auto mt-10 max-w-3xl space-y-3">
          {FAQ_ITEMS.map((item, i) => (
            <Reveal key={item.q} delay={(i % 4) * 60}>
              <details className="group rounded-2xl border border-white/8 bg-panel/70 px-5 open:border-white/15 open:bg-panel">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-left font-medium text-cloud marker:hidden">
                  <span>{item.q}</span>
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-mist transition-transform duration-300 group-open:rotate-180">
                    <Icon name="chevronDown" className="h-4 w-4" />
                  </span>
                </summary>
                <div className="pb-5 pr-10 text-sm leading-relaxed text-mist">{item.a}</div>
              </details>
            </Reveal>
          ))}

          <Reveal delay={120} className="rounded-2xl border border-white/8 bg-panel/70 p-6 text-center">
            <p className="text-sm text-mist">Ainda com dúvida?</p>
            <p className="mt-1 text-base font-semibold text-cloud">
              Crie sua conta grátis e teste com 2 vídeos — sem cartão.
            </p>
            <div className="mt-4 flex justify-center">
              <Button href={SITE.signup} iconRight="arrowRight">
                Criar meus 2 vídeos grátis
              </Button>
            </div>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
