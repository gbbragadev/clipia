"use client";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/components/landing/utils/cn";
import { Icon } from "@/components/landing/icons";
import { useInView, usePrefersReducedMotion } from "@/components/landing/lib/motion";
import { accentMap, type Accent } from "@/components/landing/lib/data";

interface VideoPhoneProps {
  src: string;
  title: string;
  accent?: Accent;
  className?: string;
  /** Controle externo (ex.: fan de celulares onde só o central toca). */
  active?: boolean;
  /** Mostra o botão de som (a narração pt-BR é argumento de venda). */
  allowSound?: boolean;
  /** Selo "Gerado no ClipIA" sobre o vídeo. */
  badge?: boolean;
  /** Frame real do vídeo: pintura imediata sem baixar o MP4 (7MB+ no hero). */
  poster?: string;
}

/**
 * Vídeo REAL do produto em moldura de celular 9:16.
 * Toca mudo quando visível, pausa fora da tela; som só por gesto do usuário.
 */
export function VideoPhone({
  src,
  title,
  accent = "coral",
  className,
  active = true,
  allowSound = false,
  badge = true,
  poster,
}: VideoPhoneProps) {
  const reduced = usePrefersReducedMotion();
  const { ref, inView } = useInView<HTMLDivElement>({ threshold: 0.3, once: false });
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [muted, setMuted] = useState(true);
  const [progress, setProgress] = useState(0);
  const [paused, setPaused] = useState(false);
  const a = accentMap[accent];

  const shouldPlay = inView && active && !paused && !reduced;

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (shouldPlay) {
      v.play().catch(() => {});
    } else {
      v.pause();
    }
  }, [shouldPlay, src]);

  return (
    <div ref={ref} className={cn("relative", className)}>
      {/* glow atrás do aparelho */}
      <div
        aria-hidden
        className="absolute -inset-6 -z-10 rounded-[3rem] opacity-50 blur-3xl"
        style={{
          background:
            accent === "coral"
              ? "radial-gradient(60% 60% at 50% 40%, rgba(255,86,56,0.28), transparent 70%)"
              : accent === "azure"
                ? "radial-gradient(60% 60% at 50% 40%, rgba(62,155,255,0.26), transparent 70%)"
                : "radial-gradient(60% 60% at 50% 40%, rgba(67,224,173,0.24), transparent 70%)",
        }}
      />
      <div className="rounded-[2.4rem] border border-white/12 bg-panel/90 p-2 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.9)]">
        <div className="relative aspect-[9/16] overflow-hidden rounded-[1.9rem] bg-ink">
          {/* key força remount ao trocar de vídeo (troca de src sem .load() trava o player) */}
          {/* preload=metadata SEMPRE: o download completo só começa no play() (inView),
              fora do caminho crítico do LCP — o antigo preload="auto" do hero puxava
              7MB de MP4 competindo com HTML/fonte/JS no 4G. O poster pinta na hora. */}
          <video
            key={src}
            ref={videoRef}
            src={src}
            poster={poster}
            muted={muted}
            loop
            playsInline
            autoPlay={shouldPlay}
            preload="metadata"
            aria-label={title}
            onTimeUpdate={(e) => {
              const v = e.currentTarget;
              if (v.duration > 0) setProgress(v.currentTime / v.duration);
            }}
            className="absolute inset-0 h-full w-full object-cover"
          />

          {/* notch */}
          <div
            aria-hidden
            className="absolute left-1/2 top-2.5 h-[18px] w-24 -translate-x-1/2 rounded-full bg-ink/90 ring-1 ring-white/10"
          />

          {/* selo de prova */}
          {badge && (
            <div className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-full border border-white/15 bg-ink/75 px-2.5 py-1 backdrop-blur-sm">
              <span className={cn("h-1.5 w-1.5 rounded-full", a.dot)} />
              <span className="font-mono text-[10px] tracking-wide text-cloud">
                Gerado no ClipIA
              </span>
            </div>
          )}

          {/* som (gesto do usuário) */}
          {allowSound && (
            <button
              type="button"
              onClick={() => {
                setMuted((m) => !m);
                setPaused(false);
                videoRef.current?.play().catch(() => {});
              }}
              aria-label={muted ? "Ativar som da narração" : "Desativar som"}
              className="absolute bottom-3 right-3 grid h-9 w-9 place-items-center rounded-full border border-white/15 bg-ink/75 text-cloud backdrop-blur-sm transition hover:bg-ink/90"
            >
              <Icon name={muted ? "volumeOff" : "volume"} className="h-4 w-4" />
            </button>
          )}

          {/* play manual (reduced motion ou pausa explícita) */}
          {(reduced || paused) && (
            <button
              type="button"
              onClick={() => {
                setPaused(false);
                videoRef.current?.play().catch(() => {});
              }}
              aria-label="Reproduzir vídeo"
              className="absolute inset-0 grid place-items-center bg-ink/40"
            >
              <span className="grid h-14 w-14 place-items-center rounded-full border border-white/20 bg-ink/80 text-cloud backdrop-blur-sm">
                <Icon name="play" className="ml-0.5 h-6 w-6" />
              </span>
            </button>
          )}

          {/* barra de progresso */}
          <div aria-hidden className="absolute inset-x-3 bottom-0.5 h-0.5 overflow-hidden rounded-full bg-white/10">
            <div
              className={cn("h-full rounded-full", a.bg)}
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
