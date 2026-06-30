"use client";
import { useInView } from "@/components/landing/lib/motion";
import { cn } from "@/components/landing/utils/cn";
import type { ElementType, ReactNode } from "react";

interface RevealProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: ElementType;
}

export function Reveal({ children, className, delay = 0, as: Tag = "div" }: RevealProps) {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <Tag
      ref={ref}
      className={cn("reveal", inView && "in", className)}
      style={{ ["--reveal-delay" as string]: `${delay}ms` }}
    >
      {children}
    </Tag>
  );
}
