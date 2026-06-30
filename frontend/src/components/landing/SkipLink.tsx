"use client";
export function SkipLink() {
  return (
    <a
      href="#conteudo"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-coral focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-ink"
    >
      Pular para o conteúdo
    </a>
  );
}
