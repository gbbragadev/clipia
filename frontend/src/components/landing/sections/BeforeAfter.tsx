"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Highlight } from "@/components/landing/ui/Highlight";
import { Button } from "@/components/landing/ui/Button";
import { Reveal } from "@/components/landing/Reveal";
import { Icon } from "@/components/landing/icons";
import { VideoPhone } from "@/components/landing/preview/VideoPhone";
import { useAb } from "@/components/landing/lib/ab";
import { useInView, useTypewriter } from "@/components/landing/lib/motion";
import { CTA_LABEL, SHOWCASE_HERO, accentMap, type ShowcaseVideo } from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

function Pair({ video, index }: { video: ShowcaseVideo; index: number }) {
  const { ref, inView } = useInView<HTMLDivElement>({ threshold: 0.35 });
  const typed = useTypewriter(video.beforeScript, inView);
  const done = typed.length === video.beforeScript.length;
  const a = accentMap[video.accent];

  return (
    <Reveal delay={index * 120}>
      <div ref={ref} className="flex h-full flex-col rounded-3xl border border-white/8 bg-panel/70 p-5">
        {/* ANTES — o tema cru digitado */}
        <div className="rounded-2xl border border-white/10 bg-ink/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="font-mono text-[10px] uppercase tracking-wider text-mist-2">
              O que entrou
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-mist">
              tema digitado
            </span>
          </div>
          <p className="mt-2.5 min-h-[3.75rem] font-mono text-sm leading-relaxed text-cloud">
            {typed}
            {!done && <span className="anim-caret text-coral">▌</span>}
          </p>
        </div>

        {/* seta IA */}
        <div className="my-4 flex items-center gap-3" aria-hidden>
          <span className="h-px flex-1 bg-gradient-to-r from-transparent via-white/15 to-white/15" />
          <span className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider", a.border, a.soft, a.text)}>
            <Icon name="sparkles" className="h-3 w-3" />
            IA
          </span>
          <span className="h-px flex-1 bg-gradient-to-l from-transparent via-white/15 to-white/15" />
        </div>

        {/* DEPOIS — o vídeo real */}
        <div className="flex flex-1 flex-col">
          <div className="flex items-center justify-between gap-3 px-1">
            <span className="font-mono text-[10px] uppercase tracking-wider text-mist-2">
              O que saiu
            </span>
            <span className={cn("font-mono text-[9px] uppercase tracking-wide", a.text)}>
              narrado + legendado
            </span>
          </div>
          <div className="mx-auto mt-3 w-full max-w-[220px]">
            <VideoPhone
              src={video.src}
              poster={video.poster}
              title={`Vídeo gerado: ${video.title}`}
              accent={video.accent}
              active={inView}
            />
          </div>
          <p className="mt-3 text-center text-sm font-medium text-cloud">{video.title}</p>
        </div>
      </div>
    </Reveal>
  );
}

export function BeforeAfter() {
  const ab = useAb();
  return (
    <section id="prova" className="relative scroll-mt-20 py-20 sm:py-24">
      <Container>
        <SectionHeading
          eyebrow="Prova real"
          eyebrowIcon="play"
          accent="coral"
          align="center"
          title={<Highlight text="Isto entrou. *Isto saiu.*" />}
          description="O texto é exatamente o tema digitado; o vídeo é o que a plataforma devolveu, gerado e editado no ClipIA. Sem take escondido, sem equipe de edição."
        />

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {SHOWCASE_HERO.map((v, i) => (
            <Pair key={v.id} video={v} index={i} />
          ))}
        </div>

        <Reveal delay={150} className="mt-10 flex flex-col items-center gap-3">
          <Button href={ab.signup("prova")} size="lg" iconRight="arrowRight">
            {CTA_LABEL}
          </Button>
          <p className="text-[13px] text-mist-2">{ab.freeClaim}</p>
        </Reveal>
      </Container>
    </section>
  );
}
