import { Icon } from "@/components/landing/icons";

const SHORTCUTS = [
  { label: "Como funciona", href: "#como-funciona" },
  { label: "Preços", href: "#preco" },
  { label: "Exemplos", href: "/exemplos" },
] as const;

export function LandingShortcuts() {
  return (
    <nav
      aria-label="Atalhos da landing"
      className="mx-auto flex w-full max-w-lg gap-2 px-5 pb-4 lg:hidden"
    >
      {SHORTCUTS.map((shortcut) => (
        <a
          key={shortcut.href}
          href={shortcut.href}
          className="flex min-w-0 flex-1 items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-panel/70 px-2 py-3 text-center text-xs font-semibold text-mist transition-colors hover:border-white/20 hover:text-cloud"
        >
          {shortcut.label}
          <Icon name="arrowRight" className="h-3.5 w-3.5 shrink-0" />
        </a>
      ))}
    </nav>
  );
}
