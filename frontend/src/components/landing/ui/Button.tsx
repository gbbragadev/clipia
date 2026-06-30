"use client";
import type { ButtonHTMLAttributes, AnchorHTMLAttributes, ReactNode } from "react";
import { cn } from "@/components/landing/utils/cn";
import { Icon, type IconName } from "@/components/landing/icons";

type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md" | "lg";

interface CommonProps {
  variant?: Variant;
  size?: Size;
  className?: string;
  children: ReactNode;
  iconRight?: IconName;
  iconLeft?: IconName;
  fullWidth?: boolean;
  href?: string;
}

type RestAttrs = Record<string, unknown> &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof CommonProps> &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof CommonProps>;

type ButtonProps = CommonProps & RestAttrs;

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-coral text-ink font-semibold hover:bg-coral-soft shadow-[0_10px_34px_-14px_rgba(255,86,56,0.85)] hover:shadow-[0_14px_40px_-12px_rgba(255,86,56,0.95)]",
  secondary:
    "bg-white/[0.05] text-cloud border border-white/10 hover:bg-white/[0.09] hover:border-white/20",
  ghost: "text-mist hover:text-cloud hover:bg-white/[0.06]",
};

const SIZES: Record<Size, string> = {
  sm: "px-3.5 py-2 text-[13px]",
  md: "px-5 py-2.5 text-sm",
  lg: "px-6 py-3.5 text-[15px]",
};

function Inner({
  iconLeft,
  iconRight,
  children,
}: {
  iconLeft?: IconName;
  iconRight?: IconName;
  children: ReactNode;
}) {
  return (
    <>
      {iconLeft && <Icon name={iconLeft} className="h-[1.05em] w-[1.05em]" />}
      <span>{children}</span>
      {iconRight && (
        <Icon
          name={iconRight}
          className="h-[1.05em] w-[1.05em] transition-transform duration-200 group-hover:translate-x-0.5"
        />
      )}
    </>
  );
}

export function Button(props: ButtonProps) {
  const {
    variant = "primary",
    size = "md",
    className,
    children,
    iconRight,
    iconLeft,
    fullWidth,
    href,
    ...rest
  } = props;

  const classes = cn(
    "group inline-flex items-center justify-center gap-2 rounded-xl transition-all duration-200 active:scale-[0.98] select-none",
    VARIANTS[variant],
    SIZES[size],
    fullWidth && "w-full",
    className
  );

  if (typeof href === "string") {
    return (
      <a href={href} className={classes} {...rest}>
        <Inner iconLeft={iconLeft} iconRight={iconRight}>
          {children}
        </Inner>
      </a>
    );
  }

  return (
    <button className={classes} {...rest}>
      <Inner iconLeft={iconLeft} iconRight={iconRight}>
        {children}
      </Inner>
    </button>
  );
}
