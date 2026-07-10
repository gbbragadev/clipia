"use client";
import type { SVGProps } from "react";
import type { ReactNode } from "react";

type IconName =
  | "sparkles"
  | "caption"
  | "layers"
  | "film"
  | "mic"
  | "download"
  | "check"
  | "play"
  | "arrowRight"
  | "menu"
  | "close"
  | "clock"
  | "chevronDown"
  | "globe"
  | "bolt"
  | "gift"
  | "card"
  | "image"
  | "shield"
  | "volume"
  | "plus"
  | "edit"
  | "wand"
  | "planet"
  | "galaxy"
  | "rocket"
  | "blackhole"
  | "star"
  | "satellite";

const P: Record<IconName, ReactNode> = {
  sparkles: (
    <>
      <path d="M12 3l1.7 4.6L18 9.3l-4.3 1.7L12 15l-1.7-4L6 9.3l4.3-1.7z" />
      <path d="M19 13l.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7z" />
    </>
  ),
  caption: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2.5" />
      <path d="M7.5 11.5h3M7.5 14.5h3M13.5 11.5h3M13.5 14.5h3" />
    </>
  ),
  layers: (
    <>
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M3 12.5l9 5 9-5" />
      <path d="M3 16.5l9 5 9-5" opacity="0.5" />
    </>
  ),
  film: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M8 4v16M16 4v16" />
      <path d="M3 9h5M3 15h5M16 9h5M16 15h5" opacity="0.6" />
    </>
  ),
  mic: (
    <>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v3M9 21h6" />
    </>
  ),
  download: (
    <>
      <path d="M12 3v12" />
      <path d="M7 11l5 4 5-4" />
      <path d="M5 21h14" />
    </>
  ),
  check: <path d="M4 12.5l5 5L20 6" />,
  play: <path d="M8 5.5l11 6.5-11 6.5z" />,
  arrowRight: (
    <>
      <path d="M4 12h15" />
      <path d="M13 6l6 6-6 6" />
    </>
  ),
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  chevronDown: <path d="M6 9.5l6 6 6-6" />,
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3c2.6 2.6 2.6 15.4 0 18M12 3c-2.6 2.6-2.6 15.4 0 18" />
    </>
  ),
  bolt: <path d="M13 3L5 13h6l-1 8 8-11h-6z" />,
  gift: (
    <>
      <path d="M4 11h16v9H4z" />
      <path d="M4 8h16v3H4z" />
      <path d="M12 8v12" />
      <path d="M12 8c-1.5-3.5-5-3-5-1.5S9.5 8 12 8zM12 8c1.5-3.5 5-3 5-1.5S14.5 8 12 8z" />
    </>
  ),
  card: (
    <>
      <rect x="3" y="6" width="18" height="12" rx="2" />
      <path d="M3 10h18" />
    </>
  ),
  image: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="8.5" cy="10" r="1.6" />
      <path d="M4 17l4.5-4 3.5 3 3-2.5 5 4" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3l8 3v6c0 5-3.4 7.8-8 9-4.6-1.2-8-4-8-9V6z" />
      <path d="M8.5 12l2.3 2.3L15.5 9.5" />
    </>
  ),
  volume: (
    <>
      <path d="M11 5L6.5 9H3.5v6H6.5L11 19z" />
      <path d="M15.5 9.5a4 4 0 0 1 0 5M18 7a7.5 7.5 0 0 1 0 10" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  edit: (
    <>
      <path d="M14 5l5 5" />
      <path d="M4 20l1-4L16 5a2 2 0 0 1 3 3L8 19z" />
    </>
  ),
  wand: (
    <>
      <path d="M15 4V2M15 16v-2M9 10H7M23 10h-2" />
      <path d="M3 21l9-9M14 7l3 3" />
    </>
  ),
  planet: (
    <>
      <circle cx="12" cy="12" r="5.5" />
      <ellipse cx="12" cy="12" rx="10" ry="3.2" transform="rotate(-22 12 12)" />
    </>
  ),
  galaxy: (
    <>
      <path d="M12 12c0-4 3-7 7-7-4 0-7-3-7-7 0 4-3 7-7 7 4 0 7 3 7 7z" transform="rotate(45 12 12)" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
    </>
  ),
  rocket: (
    <>
      <path d="M12 3c3.5 2 5 5.5 5 9.5V18H7v-5.5C7 8.5 8.5 5 12 3z" />
      <circle cx="12" cy="10" r="1.6" />
      <path d="M7 14l-2.5 2.5L7 18M17 14l2.5 2.5L17 18M9.5 18v2.5M14.5 18v2.5" />
    </>
  ),
  blackhole: (
    <>
      <circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none" />
      <ellipse cx="12" cy="12" rx="9" ry="4" />
      <ellipse cx="12" cy="12" rx="9" ry="4" transform="rotate(60 12 12)" />
      <ellipse cx="12" cy="12" rx="9" ry="4" transform="rotate(120 12 12)" />
    </>
  ),
  star: (
    <>
      <path d="M12 3l2.2 6 6.3.4-4.9 4 1.6 6.1L12 16.5 6.8 19.5l1.6-6.1-4.9-4 6.3-.4z" />
    </>
  ),
  satellite: (
    <>
      <path d="M7 7l4 4M17 17l-4-4" />
      <rect x="3" y="3" width="6" height="6" rx="1" transform="rotate(45 6 6)" />
      <rect x="15" y="15" width="6" height="6" rx="1" transform="rotate(45 18 18)" />
      <rect x="9" y="9" width="6" height="6" rx="1" />
      <path d="M9 21h6" />
    </>
  ),
};

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  className?: string;
}

export function Icon({ name, className = "h-5 w-5", ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...rest}
    >
      {P[name]}
    </svg>
  );
}

export type { IconName };
