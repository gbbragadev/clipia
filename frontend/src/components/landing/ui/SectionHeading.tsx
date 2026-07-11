"use client";
import type { ReactNode } from "react";
import { cn } from "@/components/landing/utils/cn";
import { Container } from "./Container";
import { Reveal } from "@/components/landing/Reveal";
import { Icon, type IconName } from "@/components/landing/icons";
import { accentMap, type Accent } from "@/components/landing/lib/data";

interface SectionHeadingProps {
  eyebrow?: string;
  eyebrowIcon?: IconName;
  title: ReactNode;
  description?: ReactNode;
  align?: "left" | "center";
  accent?: Accent;
  className?: string;
}

export function SectionHeading({
  eyebrow,
  eyebrowIcon = "sparkles",
  title,
  description,
  align = "left",
  accent = "coral",
  className,
}: SectionHeadingProps) {
  const a = accentMap[accent];
  const centered = align === "center";
  return (
    <div
      className={cn(
        "flex flex-col gap-4",
        centered && "items-center text-center",
        className
      )}
    >
      {eyebrow && (
        <Reveal>
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-mist",
              a.border,
              a.soft
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", a.dot)} />
            <Icon name={eyebrowIcon} className="h-3.5 w-3.5" />
            {eyebrow}
          </span>
        </Reveal>
      )}
      <Reveal delay={80}>
        <h2 className="font-display max-w-3xl text-balance text-3xl font-extrabold leading-[1.08] tracking-tight text-cloud sm:text-4xl lg:text-[2.75rem]">
          {title}
        </h2>
      </Reveal>
      {description && (
        <Reveal delay={140}>
          <p
            className={cn(
              "max-w-2xl text-pretty text-base leading-relaxed text-mist sm:text-lg",
              centered && "mx-auto"
            )}
          >
            {description}
          </p>
        </Reveal>
      )}
    </div>
  );
}

export function SectionShell({
  id,
  children,
  className,
}: {
  id?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={cn("relative py-20 sm:py-24 lg:py-28", className)}>
      <Container>{children}</Container>
    </section>
  );
}
