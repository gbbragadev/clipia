"use client";
import { Container } from "@/components/landing/ui/Container";
import { Button } from "@/components/landing/ui/Button";
import { Highlight } from "@/components/landing/ui/Highlight";
import { Icon } from "@/components/landing/icons";
import { Reveal } from "@/components/landing/Reveal";
import { useAb } from "@/components/landing/lib/ab";
import { CTA_LABEL, NICHES } from "@/components/landing/lib/data";

export function FinalCta() {
  const ab = useAb();
  const row = [...NICHES, ...NICHES];
  return (
    <section className="relative overflow-hidden py-20 sm:py-28">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div
          className="absolute left-1/2 top-1/2 h-[30rem] w-[30rem] -translate-x-1/2 -translate-y-1/2 opacity-60 blur-[130px]"
          style={{ background: "radial-gradient(circle, rgba(255,86,56,0.16), transparent 65%)" }}
        />
      </div>

      <Container>
        <Reveal className="relative overflow-hidden rounded-3xl border border-white/10 bg-panel/80 px-6 py-12 text-center sm:px-12 sm:py-16">
          <div aria-hidden className="absolute inset-0 -z-10 bg-grid opacity-30 [mask-image:radial-gradient(60%_60%_at_50%_50%,#000,transparent)]" />
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-mist">
            <span className="h-1.5 w-1.5 rounded-full bg-coral" />
            Comece grátis hoje
          </span>
          <h2 className="font-display mx-auto mt-5 max-w-2xl text-balance text-3xl font-extrabold leading-tight text-cloud sm:text-4xl lg:text-5xl">
            <Highlight text="O próximo vídeo do seu feed *pode sair daqui*." />
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-pretty text-base text-mist sm:text-lg">
            {ab.freeClaim}
          </p>
          <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button href={ab.signup("final")} size="lg" iconRight="arrowRight">
              {CTA_LABEL}
            </Button>
            <Button href="#preco" variant="secondary" size="lg">
              Ver preço
            </Button>
          </div>
          <ul className="mt-7 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[13px] text-mist">
            {["Sem cartão para começar", "MP4 vertical 9:16", "Narração em pt-BR"].map((t) => (
              <li key={t} className="flex items-center gap-1.5">
                <Icon name="check" className="h-4 w-4 text-mint" />
                {t}
              </li>
            ))}
          </ul>
          <p className="mx-auto mt-6 max-w-lg text-[12px] leading-relaxed text-mist-2">
            Sem promessa de viralizar ou de engajamento: o ClipIA acelera a criação; o resultado
            depende do tema, do nicho e dos seus ajustes no editor.
          </p>
        </Reveal>

        {/* nichos → páginas de exemplos reais */}
        <div className="relative mt-8 overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_12%,#000_88%,transparent)]">
          <div className="anim-marquee flex w-max gap-2.5">
            {row.map((n, i) => (
              <a
                key={i}
                href={n.href}
                aria-hidden={i >= NICHES.length}
                tabIndex={i >= NICHES.length ? -1 : undefined}
                className="flex shrink-0 items-center gap-1.5 rounded-full border border-white/8 bg-panel/60 px-3.5 py-1.5 text-sm text-mist transition-colors hover:border-white/20 hover:text-cloud"
              >
                <span aria-hidden>{n.emoji}</span>
                {n.label}
              </a>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}
