"use client";
import { Container } from "@/components/landing/ui/Container";
import { Logo } from "@/components/landing/Logo";
import { FOOTER_COLS, SITE } from "@/components/landing/lib/data";

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-white/8 bg-ink-2 pb-24 pt-14 lg:pb-14">
      <Container>
        <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr_1fr]">
          <div className="max-w-sm">
            <Logo />
            <p className="mt-4 text-sm leading-relaxed text-mist">
              Plataforma brasileira que transforma um tema em vídeo vertical pronto para publicar —
              com roteiro, narração em português, legendas animadas e edição.
            </p>
            <p className="mt-4 inline-flex items-center gap-2 rounded-full border border-white/8 bg-white/[0.03] px-3 py-1.5 text-[12px] text-mist">
              🇧🇷 Feito no Brasil · em português
            </p>
          </div>

          {FOOTER_COLS.map((col) => (
            <div key={col.title}>
              <h3 className="font-mono text-[11px] uppercase tracking-wider text-mist-2">
                {col.title}
              </h3>
              <ul className="mt-3 space-y-2">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      className="text-sm text-mist transition-colors hover:text-cloud"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-4 border-t border-white/8 pt-6 text-[12px] text-mist-2 sm:flex-row sm:items-center sm:justify-between">
          <p>© {year} ClipIA. Todos os direitos reservados.</p>
          <p className="max-w-md sm:text-right">
            Exemplos e imagens deste site são ilustrativos. A geração real dos vídeos acontece após
            criar a conta.
          </p>
          <a
            href={SITE.url}
            className="font-medium text-mist transition-colors hover:text-cloud"
            rel="noreferrer"
          >
            {SITE.url.replace(/^https?:\/\//, "")}
          </a>
        </div>
      </Container>
    </footer>
  );
}
