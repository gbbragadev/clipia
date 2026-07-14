"use client";
import { useState } from "react";
import { Button } from "@/components/landing/ui/Button";
import { Container } from "@/components/landing/ui/Container";
import { Highlight } from "@/components/landing/ui/Highlight";
import { Icon, type IconName } from "@/components/landing/icons";
import { Reveal } from "@/components/landing/Reveal";
import { VideoPhone } from "@/components/landing/preview/VideoPhone";
import { useAb } from "@/components/landing/lib/ab";
import { CTA_LABEL, HERO_FACTS, SHOWCASE_HERO, accentMap } from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

export function Hero() {
  const ab = useAb();
  const [idx, setIdx] = useState(0);
  const video = SHOWCASE_HERO[idx];

  return (
    <section id="top" className="relative overflow-hidden pt-28 pb-16 sm:pt-32 lg:pt-36">
      {/* background */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-grid opacity-[0.5] [mask-image:radial-gradient(70%_60%_at_50%_0%,#000,transparent)]" />
        <div
          className="absolute -top-32 left-1/2 h-[34rem] w-[34rem] -translate-x-1/2 rounded-full opacity-60 blur-[120px]"
          style={{ background: "radial-gradient(circle, rgba(255,86,56,0.16), transparent 65%)" }}
        />
        <div
          className="absolute right-0 top-40 h-[26rem] w-[26rem] opacity-50 blur-[120px]"
          style={{ background: "radial-gradient(circle, rgba(62,155,255,0.14), transparent 65%)" }}
        />
      </div>

      <Container>
        <div className="grid items-center gap-12 lg:grid-cols-[1.08fr_0.92fr] lg:gap-10">
          {/* copy */}
          <div className="flex flex-col items-start">
            <Reveal>
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-mist">
                <span className="flex h-2 w-2 items-center justify-center">
                  <span className="h-2 w-2 rounded-full bg-mint anim-pulse-ring" />
                </span>
                Plataforma brasileira · vídeo vertical com IA
              </span>
            </Reveal>

            <Reveal delay={90}>
              <h1 className="font-display mt-5 text-balance text-4xl font-extrabold leading-[1.03] tracking-tight text-cloud sm:text-5xl lg:text-[3.6rem]">
                <Highlight text={ab.headline("hero")} />
              </h1>
            </Reveal>

            <Reveal delay={160}>
              <p className="mt-5 max-w-xl text-pretty text-base leading-relaxed text-mist sm:text-lg">
                O ClipIA transforma o seu assunto em vídeo vertical com roteiro, narração em
                português e legendas sincronizadas — pronto para Reels, TikTok e Shorts. Você
                ajusta o que quiser no editor, direto no navegador.
              </p>
            </Reveal>

            <Reveal delay={230}>
              <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                <Button href={ab.signup("hero")} size="lg" iconRight="arrowRight">
                  {CTA_LABEL}
                </Button>
                <Button href="#prova" variant="secondary" size="lg" iconLeft="play">
                  Ver antes e depois
                </Button>
              </div>
            </Reveal>

            <Reveal delay={280}>
              <p className="mt-3 text-[13px] text-mist-2">{ab.freeClaim}</p>
            </Reveal>

            <Reveal delay={305}>
              <div className="mt-4 flex max-w-xl flex-wrap gap-x-4 gap-y-2 text-[12px] text-mist">
                <span className="flex items-center gap-1.5">
                  <Icon name="check" className="h-3.5 w-3.5 text-mint" />
                  Uso comercial liberado
                </span>
                <span className="flex items-center gap-1.5">
                  <Icon name="check" className="h-3.5 w-3.5 text-mint" />
                  <span>Sem marca d’água no conteúdo</span>
                  <span className="text-mist-2">· outro ClipIA de ~1,5 s</span>
                </span>
                <a
                  href="/termos#creditos-e-reembolsos"
                  className="underline decoration-white/20 underline-offset-4 transition-colors hover:text-cloud"
                >
                  Política de reembolso
                </a>
              </div>
            </Reveal>

            <Reveal delay={330}>
              <ul className="mt-7 flex flex-wrap gap-x-5 gap-y-2.5">
                {HERO_FACTS.map((f) => (
                  <li key={f.text} className="flex items-center gap-2 text-[13px] text-mist">
                    <span className="grid h-7 w-7 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-mint">
                      <Icon name={f.icon as IconName} className="h-4 w-4" />
                    </span>
                    {f.text}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>

          {/* vídeo real do produto */}
          <Reveal delay={200} className="w-full">
            <div className="mx-auto w-full max-w-[280px] sm:max-w-[320px]">
              <VideoPhone
                src={video.src}
                poster={video.poster}
                title={`Vídeo de exemplo: ${video.title}`}
                accent={video.accent}
                allowSound
              />
            </div>

            {/* troca de vídeo por nicho */}
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              {SHOWCASE_HERO.map((v, i) => {
                const a = accentMap[v.accent];
                const activeChip = i === idx;
                return (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => setIdx(i)}
                    aria-pressed={activeChip}
                    className={cn(
                      "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] transition-all duration-200",
                      activeChip
                        ? cn("text-cloud", a.border, a.soft)
                        : "border-white/10 bg-white/[0.03] text-mist hover:bg-white/[0.07] hover:text-cloud"
                    )}
                  >
                    <span aria-hidden>{v.emoji}</span>
                    {v.chip}
                  </button>
                );
              })}
            </div>

            <p className="mt-3 text-center font-mono text-[11px] text-mist-2">
              Vídeos reais gerados e editados no ClipIA · toque no alto-falante para ouvir
            </p>
          </Reveal>
        </div>
        <div id="hero" aria-hidden className="h-px w-full" />
      </Container>
    </section>
  );
}
