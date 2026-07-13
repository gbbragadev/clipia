"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Highlight } from "@/components/landing/ui/Highlight";
import { Button } from "@/components/landing/ui/Button";
import { Reveal } from "@/components/landing/Reveal";
import { Icon } from "@/components/landing/icons";
import { EditorMockup } from "@/components/landing/EditorMockup";
import { VideoPhone } from "@/components/landing/preview/VideoPhone";
import { SceneThumb } from "@/components/landing/preview/SceneThumb";
import { useAb } from "@/components/landing/lib/ab";
import { useInView, useTypewriter } from "@/components/landing/lib/motion";
import {
  CTA_LABEL,
  PERSONAS,
  SHOWCASE_HERO,
  accentMap,
  type Persona,
} from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

/* ── Visual: leque de vídeos reais (criador) ── */
function ShowcaseFan() {
  const { ref, inView } = useInView<HTMLDivElement>({ threshold: 0.3, once: false });
  const [ocean, cerebro, ia] = [SHOWCASE_HERO[1], SHOWCASE_HERO[0], SHOWCASE_HERO[2]];
  return (
    <div
      ref={ref}
      role="group"
      aria-label="Exemplos de videos em celulares"
      className="relative mx-auto grid w-full min-w-0 max-w-md grid-cols-[minmax(0,1fr)_minmax(0,1.42fr)_minmax(0,1fr)] items-center py-6"
    >
      <div className="min-w-0 w-full -rotate-6 translate-x-1 translate-y-5 opacity-80">
        <VideoPhone src={ocean.src} poster={ocean.poster} title={ocean.title} accent={ocean.accent} active={false} badge={false} />
      </div>
      <div className="z-10 min-w-0 w-full scale-[1.04]">
        <VideoPhone src={cerebro.src} poster={cerebro.poster} title={cerebro.title} accent={cerebro.accent} active={inView} />
      </div>
      <div className="min-w-0 w-full rotate-6 -translate-x-1 translate-y-5 opacity-80">
        <VideoPhone src={ia.src} poster={ia.poster} title={ia.title} accent={ia.accent} active={false} badge={false} />
      </div>
    </div>
  );
}

/* ── Visual: tema → vídeo (negócio local) — ilustrativo ── */
function PromptMock() {
  const { ref, inView } = useInView<HTMLDivElement>({ threshold: 0.35 });
  const typed = useTypewriter("5 erros ao reformar um banheiro", inView);
  const done = typed.length > 0 && typed.length === "5 erros ao reformar um banheiro".length;

  return (
    <div ref={ref} className="mx-auto w-full max-w-sm rounded-3xl border border-white/8 bg-panel/70 p-5">
      <div className="rounded-2xl border border-white/10 bg-ink/60 p-4">
        <div className="font-mono text-[10px] uppercase tracking-wider text-mist-2">
          Assunto da semana
        </div>
        <p className="mt-2 min-h-[2.5rem] font-mono text-sm text-cloud">
          {typed}
          {!done && <span className="anim-caret text-mint">▌</span>}
        </p>
        <div className="mt-3 flex justify-end">
          <span
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-all duration-500",
              done ? "bg-mint text-ink" : "bg-white/[0.06] text-mist"
            )}
          >
            <Icon name="sparkles" className="h-3.5 w-3.5" />
            Gerar vídeo
          </span>
        </div>
      </div>

      <div className="my-4 flex items-center justify-center gap-2 text-mist-2" aria-hidden>
        <Icon name="chevronDown" className={cn("h-4 w-4 transition-opacity", done ? "opacity-100 text-mint" : "opacity-40")} />
      </div>

      <div className="flex items-center gap-4">
        <div
          className={cn(
            "h-40 w-[90px] shrink-0 overflow-hidden rounded-xl ring-1 ring-white/10 transition-all duration-700",
            done ? "opacity-100" : "opacity-35"
          )}
        >
          <SceneThumb accent="mint" icon="wand" seed={2} active={done} />
        </div>
        <ul className="space-y-2.5">
          {["Narração em português", "Legendas sincronizadas", "Pronto para o perfil do negócio"].map((t) => (
            <li key={t} className="flex items-center gap-2 text-[13px] text-mist">
              <Icon name="check" className="h-4 w-4 shrink-0 text-mint" />
              {t}
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-4 text-center font-mono text-[10px] text-mist-2">
        Demonstração ilustrativa · o vídeo real é gerado na plataforma
      </p>
    </div>
  );
}

function PersonaVisual({ persona }: { persona: Persona }) {
  if (persona.visual === "editor") return <EditorMockup />;
  if (persona.visual === "prompt") return <PromptMock />;
  return <ShowcaseFan />;
}

function PersonaBlock({ persona, flip }: { persona: Persona; flip: boolean }) {
  const ab = useAb();
  const a = accentMap[persona.accent];

  return (
    <div className="relative grid w-full min-w-0 items-center gap-10 lg:grid-cols-2 lg:gap-14">
      <div className={cn("relative min-w-0", flip && "lg:order-2")}>
        <span
          aria-hidden
          className="font-display pointer-events-none absolute -left-3 -top-14 select-none text-[7rem] font-extrabold leading-none text-white/[0.04] sm:text-[8.5rem]"
        >
          {persona.index}
        </span>

        <Reveal>
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-mist",
              a.border,
              a.soft
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", a.dot)} />
            {persona.label}
          </span>
        </Reveal>

        <Reveal delay={80}>
          <h3 className="font-display mt-4 max-w-xl text-balance text-3xl font-extrabold leading-[1.06] text-cloud sm:text-4xl">
            <Highlight text={ab.headline(persona.id)} className={a.text} />
          </h3>
        </Reveal>

        {persona.paragraphs.map((p, i) => (
          <Reveal key={i} delay={140 + i * 60}>
            <p className="mt-4 max-w-xl text-pretty leading-relaxed text-mist">{p}</p>
          </Reveal>
        ))}

        <Reveal delay={280}>
          <ul className="mt-6 space-y-2.5">
            {persona.bullets.map((b) => (
              <li key={b} className="flex items-start gap-2.5 text-[14px] text-mist">
                <span className={cn("mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md", a.soft, a.text)}>
                  <Icon name="check" className="h-3.5 w-3.5" />
                </span>
                {b}
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={340}>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button href={ab.signup(`persona-${persona.id}`)} iconRight="arrowRight">
              {CTA_LABEL}
            </Button>
            <Button href="/exemplos" variant="ghost">
              Ver exemplos reais
            </Button>
          </div>
        </Reveal>
      </div>

      <Reveal delay={200} className={cn("w-full min-w-0", flip && "lg:order-1")}>
        <PersonaVisual persona={persona} />
      </Reveal>
    </div>
  );
}

export function Personas() {
  return (
    <section id="para-quem" className="relative scroll-mt-20 py-20 sm:py-24">
      <Container>
        <SectionHeading
          eyebrow="Para quem é"
          eyebrowIcon="bolt"
          accent="azure"
          align="center"
          title={<Highlight text="Feito para quem precisa postar *sem parar*." />}
          description="Três formas diferentes de usar a mesma máquina de vídeo — escolha a sua."
        />
        <div className="mt-20 space-y-24 lg:space-y-32">
          {PERSONAS.map((p, i) => (
            <PersonaBlock key={p.id} persona={p} flip={i % 2 === 1} />
          ))}
        </div>
      </Container>
    </section>
  );
}
