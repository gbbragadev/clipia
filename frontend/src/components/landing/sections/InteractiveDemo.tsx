"use client";
import { useEffect, useMemo, useState } from "react";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { Button } from "@/components/landing/ui/Button";
import { Icon } from "@/components/landing/icons";
import { PhonePreview } from "@/components/landing/preview/PhonePreview";
import { usePrefersReducedMotion } from "@/components/landing/lib/motion";
import { generateScript } from "@/components/landing/lib/script";
import { NICHES, DURATIONS, VOICES, CAPTION_STYLES, SITE } from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

// Fotos próprias da demo — nenhuma repete a galeria de exemplos.
const NICHE_IMG: Record<string, { img: string; alt: string }> = {
  curiosidades: {
    img: "https://images.pexels.com/photos/14618894/pexels-photo-14618894.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=600",
    alt: "Sol e planetas em céu estrelado representando um vídeo de curiosidades.",
  },
  motivacional: {
    img: "https://images.pexels.com/photos/1576939/pexels-photo-1576939.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=600",
    alt: "Alpinista no topo de um pico rochoso ao amanhecer representando um vídeo motivacional.",
  },
  financas: {
    img: "https://images.pexels.com/photos/6775160/pexels-photo-6775160.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=600",
    alt: "Planta crescendo em um pote de moedas representando um vídeo de finanças.",
  },
  misterio: {
    img: "https://images.pexels.com/photos/14393789/pexels-photo-14393789.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=600",
    alt: "Corredor gótico escuro iluminado por um vitral representando um vídeo de mistério.",
  },
  religioso: {
    img: "https://images.pexels.com/photos/25752564/pexels-photo-25752564.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=600",
    alt: "Bíblia aberta ao lado de uma vela acesa representando um vídeo religioso.",
  },
  humor: {
    img: "https://images.pexels.com/photos/25652088/pexels-photo-25652088.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=600",
    alt: "Duas amigas rindo juntas ao ar livre representando um vídeo de humor.",
  },
  drama: {
    img: "https://images.pexels.com/photos/13092365/pexels-photo-13092365.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=600",
    alt: "Coliseu de Roma ao pôr do sol representando um vídeo de drama histórico.",
  },
};

const WORD_MS = 300;

function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="grid grid-flow-col gap-1 rounded-xl border border-white/10 bg-ink/40 p-1">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            value === o.value ? "bg-coral text-ink" : "text-mist hover:bg-white/[0.06] hover:text-cloud"
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function InteractiveDemo() {
  const reduced = usePrefersReducedMotion();
  const [theme, setTheme] = useState("3 curiosidades sobre o espaço");
  const [niche, setNiche] = useState("curiosidades");
  const [duration, setDuration] = useState<number>(30);
  const [voiceId, setVoiceId] = useState("f-padrao");
  const [captionStyle, setCaptionStyle] = useState<"pop" | "box" | "underline">("pop");

  const [sceneIndex, setSceneIndex] = useState(0);
  const [wordIndex, setWordIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  const voice = VOICES.find((v) => v.id === voiceId)!;
  const script = useMemo(
    () => generateScript(theme, niche, duration, voice.credits),
    [theme, niche, duration, voice.credits]
  );

  const sceneCount = script.scenes.length;
  const safeScene = ((sceneIndex % sceneCount) + sceneCount) % sceneCount;
  const scene = script.scenes[safeScene];
  const words = scene.narration.split(" ");
  const img = NICHE_IMG[niche] ?? NICHE_IMG.curiosidades;

  // playback engine
  useEffect(() => {
    if (!playing || reduced) return;
    let raf = 0;
    let start = 0;
    const tick = (now: number) => {
      if (!start) start = now;
      const idx = Math.floor((now - start) / WORD_MS);
      if (idx >= words.length) {
        setSceneIndex((s) => (s + 1) % sceneCount);
        setWordIndex(0);
      } else {
        setWordIndex(idx);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, safeScene, sceneCount, reduced, words.length]);

  const activeIndex = playing ? Math.min(wordIndex, words.length - 1) : words.length - 1;

  const generate = () => {
    setSceneIndex(0);
    setWordIndex(0);
    setPlaying(!reduced);
  };

  return (
    <section id="demo" className="relative scroll-mt-20 py-20 sm:py-24">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 opacity-60"
        style={{
          background:
            "radial-gradient(50% 40% at 80% 10%, rgba(67,224,173,0.10), transparent 70%)",
        }}
      />
      <Container>
        <SectionHeading
          eyebrow="Demo interativa"
          eyebrowIcon="wand"
          accent="mint"
          title="Monte um vídeo aqui mesmo."
          description="Digite um tema, escolha o nicho, a duração e a voz. A prévia e o roteiro abaixo são uma simulação para você sentir o resultado."
        />

        <div className="mt-6 flex items-start gap-2 rounded-xl border border-mint/20 bg-mint/[0.06] px-4 py-3 text-[13px] text-mist">
          <Icon name="shield" className="mt-0.5 h-4 w-4 shrink-0 text-mint" />
          <span>
            <strong className="text-cloud">Simulação ilustrativa</strong> — a geração real acontece
            após criar a conta.
          </span>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
          {/* CONTROLS */}
          <Reveal className="rounded-2xl border border-white/8 bg-panel/70 p-5 sm:p-6">
            <div className="space-y-5">
              <div>
                <label htmlFor="theme" className="font-mono text-[11px] uppercase tracking-wider text-mist">
                  Tema do vídeo
                </label>
                <div className="mt-2 flex items-center gap-2 rounded-xl border border-white/10 bg-ink/50 px-3 py-2.5 focus-within:border-coral/50">
                  <Icon name="sparkles" className="h-4 w-4 shrink-0 text-coral" />
                  <input
                    id="theme"
                    value={theme}
                    onChange={(e) => setTheme(e.target.value)}
                    placeholder="Ex.: 3 curiosidades sobre o espaço"
                    className="w-full bg-transparent text-sm text-cloud placeholder:text-mist-2 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <span className="font-mono text-[11px] uppercase tracking-wider text-mist">Nicho</span>
                <div className="mt-2 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
                  {NICHES.map((n) => (
                    <button
                      key={n.id}
                      type="button"
                      aria-pressed={niche === n.id}
                      onClick={() => setNiche(n.id)}
                      className={cn(
                        "flex items-center gap-1.5 rounded-lg border px-2.5 py-2 text-left text-[12px] transition-colors",
                        niche === n.id
                          ? "border-coral/50 bg-coral/[0.08] text-cloud"
                          : "border-white/10 bg-white/[0.02] text-mist hover:border-white/20 hover:text-cloud"
                      )}
                    >
                      <span aria-hidden>{n.emoji}</span>
                      <span className="truncate">{n.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <span className="font-mono text-[11px] uppercase tracking-wider text-mist">Duração</span>
                  <div className="mt-2">
                    <Segmented
                      label="Duração"
                      value={duration}
                      onChange={setDuration}
                      options={DURATIONS.map((d) => ({ value: d.s, label: d.label }))}
                    />
                  </div>
                </div>
                <div>
                  <span className="font-mono text-[11px] uppercase tracking-wider text-mist">Legenda</span>
                  <div className="mt-2">
                    <Segmented
                      label="Estilo de legenda"
                      value={captionStyle}
                      onChange={setCaptionStyle}
                      options={CAPTION_STYLES.map((c) => ({ value: c.id, label: c.label }))}
                    />
                  </div>
                </div>
              </div>

              <div>
                <label htmlFor="voice" className="font-mono text-[11px] uppercase tracking-wider text-mist">
                  Narração (pt-BR)
                </label>
                <div className="relative mt-2">
                  <select
                    id="voice"
                    value={voiceId}
                    onChange={(e) => setVoiceId(e.target.value)}
                    className="w-full appearance-none rounded-xl border border-white/10 bg-ink/50 px-3 py-2.5 text-sm text-cloud focus:border-coral/50 focus:outline-none"
                  >
                    {VOICES.map((v) => (
                      <option key={v.id} value={v.id} className="bg-panel text-cloud">
                        {v.label} · {v.credits} crédito{v.credits > 1 ? "s" : ""}
                      </option>
                    ))}
                  </select>
                  <Icon
                    name="chevronDown"
                    className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-mist"
                  />
                </div>
              </div>

              <Button onClick={generate} size="lg" fullWidth iconRight="sparkles">
                Gerar e reproduzir
              </Button>

              <div className="flex items-center justify-between rounded-xl border border-white/8 bg-ink/40 px-3 py-2.5 text-[12px]">
                <span className="flex items-center gap-1.5 text-mist">
                  <Icon name="card" className="h-4 w-4 text-mint" />
                  Custo deste vídeo
                </span>
                <span className="font-semibold text-cloud">
                  {voice.credits} crédito{voice.credits > 1 ? "s" : ""}{" "}
                  <span className="font-normal text-mist-2">· por voz, não por duração</span>
                </span>
              </div>
            </div>
          </Reveal>

          {/* OUTPUT */}
          <div className="flex flex-col gap-5">
            <Reveal className="flex flex-col items-center rounded-2xl border border-white/8 bg-panel/70 p-5">
              <PhonePreview
                image={img.img}
                alt={img.alt}
                words={words}
                activeIndex={activeIndex}
                captionStyle={captionStyle}
                nicheLabel={NICHES.find((n) => n.id === niche)?.label}
                durationLabel={`${duration}s`}
                progress={playing ? (wordIndex + 1) / words.length : 1}
                showPlay={!playing}
                onPlay={() => setPlaying(true)}
                className="w-[230px] sm:w-[250px]"
              />

              {/* transport */}
              <div className="mt-4 flex w-full max-w-[260px] items-center justify-center gap-2">
                <button
                  type="button"
                  aria-label="Cena anterior"
                  onClick={() => {
                    setPlaying(false);
                    setSceneIndex((s) => (s - 1 + sceneCount) % sceneCount);
                  }}
                  className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-mist transition-colors hover:text-cloud"
                >
                  <Icon name="chevronDown" className="h-4 w-4 rotate-90" />
                </button>
                <Button
                  onClick={() => setPlaying((p) => !p)}
                  variant="secondary"
                  size="sm"
                  iconLeft={playing ? undefined : "play"}
                  className="min-w-[7rem]"
                >
                  {playing ? "Pausar" : "Reproduzir"}
                </Button>
                <button
                  type="button"
                  aria-label="Próxima cena"
                  onClick={() => {
                    setPlaying(false);
                    setSceneIndex((s) => (s + 1) % sceneCount);
                  }}
                  className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-mist transition-colors hover:text-cloud"
                >
                  <Icon name="chevronDown" className="h-4 w-4 -rotate-90" />
                </button>
              </div>
              <p className="mt-2 font-mono text-[11px] text-mist-2">
                Cena {safeScene + 1} de {sceneCount}
              </p>
            </Reveal>

            <Reveal delay={80} className="rounded-2xl border border-white/8 bg-panel/70 p-5">
              <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-mist">
                <Icon name="edit" className="h-3.5 w-3.5 text-coral" />
                Roteiro simulado
              </div>
              <h3 className="mt-2 text-lg font-semibold leading-snug text-cloud">{script.hook}</h3>
              <ol className="mt-4 space-y-2">
                {script.scenes.map((s, i) => (
                  <li key={i}>
                    <button
                      type="button"
                      onClick={() => {
                        setPlaying(false);
                        setSceneIndex(i);
                      }}
                      className={cn(
                        "flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-colors",
                        i === safeScene
                          ? "border-coral/40 bg-coral/[0.06]"
                          : "border-white/8 bg-white/[0.02] hover:border-white/15"
                      )}
                    >
                      <span
                        className={cn(
                          "grid h-6 w-6 shrink-0 place-items-center rounded-md font-mono text-[11px]",
                          i === safeScene ? "bg-coral text-ink" : "bg-white/[0.06] text-mist"
                        )}
                      >
                        {i + 1}
                      </span>
                      <span className="min-w-0">
                        <span className="block font-mono text-[10px] uppercase tracking-wide text-coral">
                          {s.caption}
                        </span>
                        <span className="block text-[13px] leading-snug text-mist">{s.narration}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ol>

              <div className="mt-4 border-t border-white/8 pt-4">
                <Button href={SITE.signup} variant="secondary" size="md" fullWidth iconRight="arrowRight">
                  Criar a conta e gerar de verdade
                </Button>
              </div>
            </Reveal>
          </div>
        </div>
      </Container>
    </section>
  );
}
