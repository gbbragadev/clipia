"use client";
import { useEffect, useState } from "react";
import { cn } from "@/components/landing/utils/cn";
import { Logo } from "@/components/landing/Logo";
import { Button } from "@/components/landing/ui/Button";
import { Icon } from "@/components/landing/icons";
import { NAV_LINKS, SITE } from "@/components/landing/lib/data";

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled
          ? "border-b border-white/8 bg-ink/85 backdrop-blur-xl"
          : "border-b border-transparent bg-transparent"
      )}
    >
      <nav className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-5 sm:px-6 lg:px-8">
        <a href="#top" aria-label="ClipIA — início" className="shrink-0">
          <Logo />
        </a>

        <div className="hidden items-center gap-1 lg:flex">
          {NAV_LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="rounded-lg px-3 py-2 text-sm text-mist transition-colors hover:bg-white/[0.06] hover:text-cloud"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="hidden items-center gap-2 lg:flex">
          <Button href={SITE.login} variant="ghost" size="sm">
            Entrar
          </Button>
          <Button href={SITE.signup} variant="primary" size="sm" iconRight="arrowRight">
            Criar 2 vídeos grátis
          </Button>
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls="menu-mobile"
          aria-label={open ? "Fechar menu" : "Abrir menu"}
          className="grid h-10 w-10 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-cloud lg:hidden"
        >
          <Icon name={open ? "close" : "menu"} className="h-5 w-5" />
        </button>
      </nav>

      {/* mobile menu */}
      <div
        id="menu-mobile"
        className={cn(
          "overflow-hidden border-t border-white/8 bg-ink/95 backdrop-blur-xl transition-[max-height,opacity] duration-300 lg:hidden",
          open ? "max-h-[26rem] opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="space-y-1 px-5 py-4">
          {NAV_LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="block rounded-lg px-3 py-3 text-base text-mist transition-colors hover:bg-white/[0.06] hover:text-cloud"
            >
              {l.label}
            </a>
          ))}
          <div className="grid gap-2 pt-3">
            <Button href={SITE.signup} variant="primary" size="lg" fullWidth iconRight="arrowRight">
              Criar meus 2 vídeos grátis
            </Button>
            <Button href={SITE.login} variant="secondary" size="md" fullWidth>
              Entrar
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}
