"use client";
import { cn } from "@/components/landing/utils/cn";

export function Logo({
  className,
  withWordmark = true,
}: {
  className?: string;
  withWordmark?: boolean;
}) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span className="relative grid h-9 w-9 place-items-center overflow-hidden rounded-xl border border-white/10 bg-panel-2">
        <span className="absolute inset-0 bg-gradient-to-br from-coral/25 via-transparent to-azure/15" />
        <svg viewBox="0 0 24 24" className="relative h-4 w-4" aria-hidden="true">
          <path d="M8 5.2l10 6.8-10 6.8z" fill="#ff5638" />
        </svg>
        <span className="absolute bottom-1 right-1 h-1.5 w-1.5 rounded-full bg-mint" />
      </span>
      {withWordmark && (
        <span className="font-display text-[1.05rem] font-bold tracking-tight">
          <span className="text-cloud">Clip</span>
          <span className="text-coral">IA</span>
        </span>
      )}
    </span>
  );
}
