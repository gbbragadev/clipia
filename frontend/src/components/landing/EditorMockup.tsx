"use client";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/components/landing/utils/cn";
import { Icon } from "@/components/landing/icons";
import { PhonePreview } from "@/components/landing/preview/PhonePreview";
import { SceneThumb } from "@/components/landing/preview/SceneThumb";
import { usePrefersReducedMotion } from "@/components/landing/lib/motion";
import { HERO_SCRIPT } from "@/components/landing/lib/script";
import type { Accent } from "@/components/landing/lib/data";

const THEME = "3 curiosidades sobre o espaço";
const TYPE_MS = 1700;
const SCRIPT_MS = 2400;
const NARR_MS = 1400;
const BUILD_MS = TYPE_MS + SCRIPT_MS + NARR_MS;
const PLAY_MS = 5200;

const WAVE = Array.from({ length: 16 }, (_, i) => 30 + Math.abs(Math.sin(i * 1.7)) * 70);

function fmt(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  return `0:${String(s).padStart(2, "0")}`;
}

export function EditorMockup() {
  const reduced = usePrefersReducedMotion();
  const scenes = HERO_SCRIPT.scenes;
  const [clock, setClock] = useState(0);
  const [visible, setVisible] = useState(true);
  const rootRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);
  const accRef = useRef(0);
  const startRef = useRef(0);
  const lastRef = useRef(0);

  // Pause the animation when the editor is off-screen.
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (reduced) {
      setClock(BUILD_MS + PLAY_MS * 0.4);
      return;
    }
    if (!visible) return;
    startRef.current = performance.now();
    lastRef.current = 0;
    const tick = (now: number) => {
      if (now - lastRef.current >= 33) {
        lastRef.current = now;
        setClock(accRef.current + (now - startRef.current));
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      accRef.current += performance.now() - startRef.current;
    };
  }, [reduced, visible]);

  // ---- derived state ----
  const tType = Math.min(1, clock / TYPE_MS);
  const typedLen = reduced ? THEME.length : Math.max(0, Math.round(tType * THEME.length));
  const typedTheme = THEME.slice(0, typedLen);

  const per = SCRIPT_MS / scenes.length;
  const scenesShown = reduced
    ? scenes.length
    : clock < TYPE_MS
    ? 0
    : Math.min(scenes.length, Math.floor((clock - TYPE_MS) / per) + 1);

  const narrationReady = reduced ? true : clock >= TYPE_MS + SCRIPT_MS;
  const playing = reduced ? true : clock >= BUILD_MS;

  const loopClock = Math.max(0, clock - BUILD_MS);
  const cycle = Math.floor(loopClock / PLAY_MS);
  const loopT = loopClock % PLAY_MS / PLAY_MS;
  const playhead = reduced ? 0.42 : loopT;
  const activeScene = reduced ? 0 : cycle % scenes.length;

  const sceneCount = scenes.length;
  const sceneLocal =
    reduced ? 0.6 : Math.min(1, Math.max(0, (playhead - activeScene / sceneCount) * sceneCount));
  const currentScene = scenes[activeScene];
  const words = currentScene.narration.split(" ");
  const wordIndex = reduced
    ? words.length - 1
    : Math.min(words.length - 1, Math.floor(sceneLocal * words.length));

  const status = playing
    ? "Pronto"
    : clock < TYPE_MS
    ? "Digitando tema"
    : clock < TYPE_MS + SCRIPT_MS
    ? "Gerando roteiro"
    : "Sincronizando narração";

  const totalSec = 30;
  const curSec = playhead * totalSec;

  return (
    <div className="relative">
      {/* ambient glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-6 -z-10 opacity-70 blur-2xl"
        style={{
          background:
            "radial-gradient(60% 50% at 70% 20%, rgba(255,86,56,0.18), transparent 70%), radial-gradient(50% 50% at 20% 80%, rgba(62,155,255,0.14), transparent 70%)",
        }}
      />
      <div className="overflow-hidden rounded-2xl border border-white/10 bg-panel/90 shadow-[0_40px_90px_-40px_rgba(0,0,0,0.9)] backdrop-blur-sm">
        {/* toolbar */}
        <div className="flex items-center justify-between border-b border-white/8 bg-ink/50 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
            <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
            <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
            <span className="ml-2 font-mono text-[11px] text-mist">ClipIA · Editor</span>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-panel px-2.5 py-1 font-mono text-[10px] text-cloud">
            <span className={cn("h-1.5 w-1.5 rounded-full", playing ? "bg-mint" : "bg-coral anim-pulse-ring")} />
            {status}
          </span>
        </div>

        <div className="bg-grid p-4">
          <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
            {/* LEFT: theme + storyboard */}
            <div className="flex flex-col gap-3">
              <div className="rounded-xl border border-white/10 bg-ink/40 p-3">
                <div className="font-mono text-[10px] uppercase tracking-wider text-mist">
                  Tema do vídeo
                </div>
                <div className="mt-1.5 flex items-center gap-2 font-display text-sm text-cloud">
                  <Icon name="sparkles" className="h-4 w-4 shrink-0 text-mint" />
                  <span className="truncate">{typedTheme}</span>
                  {!playing && <span className="anim-caret -ml-1 text-coral">▌</span>}
                </div>
              </div>

              <div className="font-mono text-[10px] uppercase tracking-wider text-mist">
                Storyboard · {scenesShown}/{scenes.length} cenas
              </div>

              <div className="flex flex-col gap-2">
                {scenes.slice(0, scenesShown).map((s, i) => {
                  const active = playing && i === activeScene;
                  return (
                    <div
                      key={i}
                      className={cn(
                        "flex items-center gap-2.5 rounded-xl border p-2 transition-all duration-300",
                        active
                          ? "border-coral/50 bg-coral/[0.07]"
                          : "border-white/8 bg-panel/60"
                      )}
                    >
                      <div className="relative h-12 w-9 shrink-0 overflow-hidden rounded-md ring-1 ring-white/10">
                        <SceneThumb
                          accent={(s.accent ?? "azure") as Accent}
                          icon={s.icon ?? "planet"}
                          seed={i}
                          label={i + 1}
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-mono text-[10px] uppercase tracking-wide text-coral">
                          {s.caption}
                        </div>
                        <div className="line-clamp-1 text-[11px] leading-snug text-mist">
                          {s.narration}
                        </div>
                      </div>
                      {active && (
                        <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-coral text-ink">
                          <svg viewBox="0 0 24 24" className="ml-0.5 h-2.5 w-2.5" aria-hidden="true">
                            <path d="M8 5.5l11 6.5-11 6.5z" fill="currentColor" />
                          </svg>
                        </span>
                      )}
                    </div>
                  );
                })}
                {scenesShown < scenes.length && (
                  <div className="anim-shimmer relative flex items-center gap-2.5 overflow-hidden rounded-xl border border-white/8 bg-panel/40 p-2">
                    <div className="h-12 w-9 shrink-0 rounded-md bg-white/5" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-2 w-20 rounded bg-white/5" />
                      <div className="h-2 w-full rounded bg-white/5" />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT: preview + voice */}
            <div className="flex flex-col items-center gap-3">
              <PhonePreview
                alt="Prévia vertical de um vídeo sobre o espaço, com legenda animada."
                background={
                  <SceneThumb
                    key={activeScene}
                    accent={(currentScene.accent ?? "azure") as Accent}
                    icon={currentScene.icon ?? "planet"}
                    seed={activeScene}
                    active={playing}
                    className={cn("h-full w-full", playing && "anim-scene-fade")}
                  />
                }
                words={narrationReady ? words : []}
                activeIndex={narrationReady ? wordIndex : -1}
                captionStyle="pop"
                nicheLabel="Curiosidades"
                durationLabel="9:16"
                progress={playing ? playhead : undefined}
                timecode={playing ? fmt(curSec) : undefined}
                className="w-[220px] sm:w-[240px]"
              />
              <div className="flex w-full items-center gap-2 rounded-xl border border-white/10 bg-panel px-3 py-2">
                <Icon name="mic" className="h-4 w-4 shrink-0 text-azure" />
                <div className="min-w-0">
                  <div className="text-[11px] font-medium text-cloud">Narração pt-BR</div>
                  <div className="text-[10px] text-mist">Voz feminina · natural</div>
                </div>
                <div className="ml-auto flex h-5 items-end gap-[2px]">
                  {WAVE.map((h, i) => (
                    <span
                      key={i}
                      className={cn(
                        "w-[2px] rounded-full bg-azure/70",
                        narrationReady ? "anim-equalize" : "opacity-40"
                      )}
                      style={{
                        height: `${h}%`,
                        animationDelay: `${(i % 8) * 90}ms`,
                        animationDuration: `${900 + (i % 5) * 120}ms`,
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* TIMELINE */}
          <div className="mt-4 rounded-xl border border-white/10 bg-ink/40 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-mist">
                Timeline
              </span>
              <span className="font-mono text-[10px] text-cloud">
                {playing ? fmt(curSec) : "--"} / {fmt(totalSec)}
              </span>
            </div>

            {/* desktop horizontal tracks */}
            <div className="relative hidden space-y-1.5 sm:block">
              {playing && (
                <div
                  className="absolute top-0 bottom-0 z-10 w-px bg-coral shadow-[0_0_8px_rgba(255,86,56,0.8)] transition-[left] duration-100 ease-linear"
                  style={{ left: `${playhead * 100}%` }}
                />
              )}
              {[
                { label: "Vídeo", render: "blocks" },
                { label: "Narração", render: "wave" },
                { label: "Legenda", render: "caps" },
              ].map((tr) => (
                <div key={tr.label} className="flex items-center gap-2">
                  <span className="w-14 shrink-0 font-mono text-[9px] uppercase text-mist-2">
                    {tr.label}
                  </span>
                  <div className="relative flex h-5 flex-1 gap-1 overflow-hidden rounded-md bg-white/[0.03] p-0.5">
                    {scenes.map((s, i) => (
                      <div
                        key={i}
                        className={cn(
                          "h-full flex-1 rounded-[3px]",
                          playing && i === activeScene
                            ? "bg-coral/30 ring-1 ring-coral/50"
                            : "bg-white/[0.06]"
                        )}
                      >
                        {tr.render === "wave" && (
                          <div className="flex h-full items-end gap-px px-0.5">
                            {WAVE.slice(0, 8).map((h, k) => (
                              <span
                                key={k}
                                className={cn(
                                  "flex-1 rounded-full",
                                  narrationReady ? "anim-equalize bg-azure/50" : "bg-azure/20"
                                )}
                                style={{ height: `${h}%`, animationDelay: `${k * 80}ms` }}
                              />
                            ))}
                          </div>
                        )}
                        {tr.render === "caps" && (
                          <div className="flex h-full items-center justify-center px-0.5">
                            <span className="line-clamp-1 font-mono text-[7px] uppercase text-mist">
                              {s.caption.split(" ")[0]}
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* mobile vertical sequence */}
            <ol className="space-y-0 sm:hidden">
              {scenes.map((s, i) => {
                const done = playing && i < activeScene;
                const active = playing && i === activeScene;
                return (
                  <li key={i} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <span
                        className={cn(
                          "grid h-6 w-6 place-items-center rounded-full border font-mono text-[10px]",
                          active
                            ? "border-coral bg-coral text-ink"
                            : done
                            ? "border-mint/50 bg-mint/15 text-mint"
                            : "border-white/15 text-mist-2"
                        )}
                      >
                        {done ? "✓" : i + 1}
                      </span>
                      {i < scenes.length - 1 && (
                        <span className={cn("my-0.5 h-4 w-px", done ? "bg-mint/40" : "bg-white/10")} />
                      )}
                    </div>
                    <div className="pb-3">
                      <div className="font-mono text-[10px] uppercase tracking-wide text-coral">
                        {s.caption}
                      </div>
                      <div className="text-[11px] leading-snug text-mist">{s.narration}</div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}
