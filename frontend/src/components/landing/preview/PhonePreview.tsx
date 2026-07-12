"use client";
import type { ReactNode } from "react";
import { cn } from "@/components/landing/utils/cn";
import { Icon } from "@/components/landing/icons";

type CaptionStyle = "pop" | "box" | "underline";

export function Caption({
  words,
  activeIndex,
  style = "pop",
  className,
}: {
  words: string[];
  activeIndex: number;
  style?: CaptionStyle;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "flex flex-wrap items-baseline justify-center gap-x-1.5 gap-y-0.5 text-center font-display font-extrabold uppercase leading-[1.04] tracking-tight drop-shadow-[0_2px_8px_rgba(0,0,0,0.65)]",
        className
      )}
    >
      {words.map((w, i) => {
        const state = i < activeIndex ? "past" : i === activeIndex ? "active" : "future";
        const base = "inline-block transition-all duration-200 ease-out";
        let cls = base;
        if (style === "pop") {
          cls +=
            state === "active"
              ? " scale-110 text-coral"
              : state === "past"
              ? " text-cloud/85"
              : " text-cloud/25";
        } else if (style === "box") {
          cls +=
            state === "active"
              ? " rounded-md bg-cloud px-1.5 text-ink"
              : state === "past"
              ? " text-cloud/85"
              : " text-cloud/25";
        } else {
          cls +=
            state === "active"
              ? " border-b-2 border-mint pb-0.5 text-mint"
              : state === "past"
              ? " text-cloud/85"
              : " text-cloud/25";
        }
        return (
          <span key={i} className={cls}>
            {w}
          </span>
        );
      })}
    </span>
  );
}

interface PhonePreviewProps {
  image?: string;
  alt?: string;
  background?: ReactNode;
  words: string[];
  activeIndex: number;
  captionStyle?: CaptionStyle;
  nicheLabel?: string;
  voiceLabel?: string;
  durationLabel?: string;
  progress?: number;
  timecode?: string;
  className?: string;
  showPlay?: boolean;
  onPlay?: () => void;
}

export function PhonePreview({
  image,
  alt = "Prévia de vídeo vertical no formato Shorts gerado pelo ClipIA",
  background,
  words,
  activeIndex,
  captionStyle = "pop",
  nicheLabel,
  voiceLabel,
  durationLabel,
  progress,
  timecode,
  className,
  showPlay = false,
  onPlay,
}: PhonePreviewProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[1.35rem] border border-white/10 bg-panel-2 shadow-[0_30px_60px_-25px_rgba(0,0,0,0.9)]",
        className
      )}
    >
      <div className="relative aspect-[9/16] w-full">
        {background ? (
          <div className="absolute inset-0">{background}</div>
        ) : (
          <img
            src={image}
            alt={alt}
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover"
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-b from-ink/55 via-transparent to-ink/90" />

        {typeof progress === "number" && (
          <div className="absolute inset-x-0 top-0 z-10 h-[3px] bg-white/10">
            <div
              className="h-full w-full origin-left bg-coral transition-transform duration-150 ease-linear"
              style={{ transform: `scaleX(${Math.min(1, Math.max(0, progress))})` }}
            />
          </div>
        )}

        <div className="absolute inset-x-0 top-0 flex items-center justify-between p-2.5">
          {nicheLabel && (
            <span className="inline-flex items-center gap-1 rounded-full bg-ink/55 px-2 py-1 font-mono text-[10px] text-cloud backdrop-blur-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-mint" />
              {nicheLabel}
            </span>
          )}
          {durationLabel && (
            <span className="rounded-full bg-ink/55 px-2 py-1 font-mono text-[10px] text-mist backdrop-blur-sm">
              {durationLabel}
            </span>
          )}
        </div>

        {timecode && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-[10px] text-cloud/70 [writing-mode:vertical-rl]">
            {timecode}
          </span>
        )}

        <div className="absolute inset-x-0 bottom-0 p-3 pb-4">
          <Caption
            words={words}
            activeIndex={activeIndex}
            style={captionStyle}
            className="text-[0.95rem] sm:text-base"
          />
          {voiceLabel && (
            <div className="mt-2.5 flex justify-center">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-ink/55 px-2.5 py-1 text-[10px] text-mist backdrop-blur-sm">
                <Icon name="mic" className="h-3 w-3 text-azure" />
                {voiceLabel}
              </span>
            </div>
          )}
        </div>

        {showPlay && (
          <button
            type="button"
            onClick={onPlay}
            aria-label="Reproduzir prévia"
            className="absolute inset-0 z-20 grid place-items-center"
          >
            <span className="grid h-14 w-14 place-items-center rounded-full bg-coral text-ink shadow-lg transition-transform hover:scale-105 active:scale-95">
              <svg viewBox="0 0 24 24" className="ml-0.5 h-6 w-6" aria-hidden="true">
                <path d="M8 5.5l11 6.5-11 6.5z" fill="currentColor" />
              </svg>
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
