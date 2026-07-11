"use client";
import { cn } from "@/components/landing/utils/cn";
import { Icon, type IconName } from "@/components/landing/icons";
import type { Accent } from "@/components/landing/lib/data";

// Accent -> core rgb triplet (matches tokens in globals.css @theme).
const RGB: Record<Accent, string> = {
  coral: "255, 86, 56",
  azure: "62, 155, 255",
  mint: "67, 224, 173",
};

// Gradient anchor variation per scene seed — keeps each thumb visually unique
// while staying inside the same accent palette.
const ANCHORS = [
  { x: 30, y: 25 },
  { x: 70, y: 30 },
  { x: 50, y: 60 },
  { x: 25, y: 70 },
  { x: 75, y: 55 },
  { x: 50, y: 35 },
];

interface SceneThumbProps {
  accent: Accent;
  icon: string;
  seed?: number;
  label?: number;
  active?: boolean;
  className?: string;
}

/**
 * Procedural 9:16 thumbnail: neon radial gradient + themed space icon + grain.
 * Decorative by design (the real media is generated after sign-up), so the
 * wrapper is aria-hidden. Used in the Hero storyboard and phone preview.
 */
export function SceneThumb({
  accent,
  icon,
  seed = 0,
  label,
  active = false,
  className,
}: SceneThumbProps) {
  const rgb = RGB[accent];
  const anchor = ANCHORS[seed % ANCHORS.length];

  return (
    <div
      aria-hidden
      className={cn(
        "relative h-full w-full overflow-hidden bg-ink-2",
        active && "scene-active",
        className
      )}
    >
      {/* base radial gradient (neon glow in accent color) */}
      <div
        className="absolute inset-0 transition-transform duration-700 ease-out"
        style={{
          background: `radial-gradient(120% 120% at ${anchor.x}% ${anchor.y}%, rgba(${rgb}, 0.55) 0%, rgba(${rgb}, 0.18) 38%, rgba(8, 9, 15, 0.92) 78%)`,
        }}
      />
      {/* secondary offset glow for depth */}
      <div
        className="absolute inset-0 opacity-70"
        style={{
          background: `radial-gradient(80% 60% at ${100 - anchor.x}% ${100 - anchor.y}%, rgba(${rgb}, 0.22), transparent 60%)`,
        }}
      />
      {/* grain */}
      <div className="scene-grain absolute inset-0 opacity-[0.06] mix-blend-soft-light" />
      {/* themed icon, centered, with glow */}
      <div className="absolute inset-0 grid place-items-center">
        <span
          className="block"
          style={{
            color: `rgb(${rgb})`,
            filter: `drop-shadow(0 0 14px rgba(${rgb}, 0.65)) drop-shadow(0 0 4px rgba(${rgb}, 0.9))`,
          }}
        >
          <Icon name={icon as IconName} className="h-1/3 w-1/3 max-h-[64px] min-h-[28px]" strokeWidth={1.4} />
        </span>
      </div>
      {/* legibility scrim bottom */}
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-ink/85 to-transparent" />
      {typeof label === "number" && (
        <span className="absolute bottom-0 left-0 bg-ink/70 px-1 font-mono text-[8px] text-cloud">
          {String(label).padStart(2, "0")}
        </span>
      )}
    </div>
  );
}
