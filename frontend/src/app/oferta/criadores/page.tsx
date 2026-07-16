import type { Metadata } from "next";
import Link from "next/link";

import Logo from "@/components/brand/Logo";
import { Button } from "@/components/landing/ui/Button";
import { canonicalUrl } from "@/lib/site";

const CAMPAIGN_CTA =
  "/auth/register?offer=creator20_v1&utm_source=meta&utm_medium=paid_social&utm_campaign=clipia_creator20_pilot";

export const metadata: Metadata = {
  title: "20 créditos para transformar ideias em vídeos — ClipIA",
  description:
    "Oferta para criadores: confirme seu e-mail e receba 20 créditos no total para criar vídeos curtos com roteiro, voz e legendas.",
  alternates: { canonical: canonicalUrl("/oferta/criadores") },
  openGraph: {
    title: "Sua ideia pronta para publicar com 20 créditos no ClipIA",
    description: "Crie vídeos curtos com roteiro, narração e legendas. A oferta é aplicada após a confirmação do e-mail.",
    url: canonicalUrl("/oferta/criadores"),
    siteName: "ClipIA",
    locale: "pt_BR",
    type: "website",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "ClipIA para criadores" }],
  },
};

const STEPS = [
  ["1", "Conte sua ideia", "Digite o assunto e escolha o estilo do vídeo."],
  ["2", "A IA monta a base", "Roteiro, narração em português, mídia e legendas sincronizadas."],
  ["3", "Revise e publique", "Ajuste no editor, exporte o MP4 e use onde preferir."],
] as const;

const FAQ = [
  ["Quando os 20 créditos entram?", "Depois que você cria a conta por esta página e confirma o e-mail. O saldo total creditado é 20."],
  ["Como os 20 créditos são formados?", "São 2 créditos de boas-vindas + 18 créditos da oferta creator20_v1."],
  ["Os créditos expiram?", "Não. Os créditos recebidos ficam disponíveis na sua conta até serem usados."],
  ["A oferta acumula com indicação?", "Não. Esta oferta de aquisição não acumula com o bônus de ativação por indicação."],
  ["Preciso autorizar mensuração de anúncios?", "Não. Essa autorização aparece separada no cadastro, começa desmarcada e é opcional."],
] as const;

export default function CreatorOfferPage() {
  return (
    <div className="min-h-screen bg-ink text-cloud antialiased">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
        <Link href="/" aria-label="ClipIA — início">
          <Logo />
        </Link>
        <Button href={CAMPAIGN_CTA} size="sm" iconRight="arrowRight">
          Criar minha conta
        </Button>
      </header>

      <main>
        <section className="relative isolate overflow-hidden px-5 pb-20 pt-14 sm:px-8 sm:pb-28 sm:pt-24">
          <div className="pointer-events-none absolute left-1/2 top-8 -z-10 h-[420px] w-[720px] -translate-x-1/2 rounded-full bg-coral/15 blur-[130px]" />
          <div className="mx-auto max-w-4xl text-center">
            <p className="mb-5 text-sm font-semibold uppercase tracking-[0.22em] text-coral">
              ClipIA para criadores
            </p>
            <h1 className="text-balance font-display text-4xl font-extrabold leading-[1.05] sm:text-6xl lg:text-7xl">
              Transforme uma ideia em vídeo pronto para publicar
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-balance text-lg leading-relaxed text-mist sm:text-xl">
              Confirme seu e-mail e receba <strong className="text-cloud">20 créditos</strong> para criar vídeos
              curtos com roteiro, voz em português, mídia e legendas.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button href={CAMPAIGN_CTA} size="lg" iconRight="arrowRight">
                Começar com 20 créditos
              </Button>
              <Button href="/exemplos" variant="secondary" size="lg">
                Ver vídeos criados
              </Button>
            </div>
            <p className="mx-auto mt-5 max-w-xl text-sm leading-relaxed text-mist-2">
              Oferta creator20_v1 para uma conta elegível: 2 créditos de boas-vindas + 18 créditos da oferta,
              liberados juntos após a confirmação do e-mail. Sem assinatura obrigatória.
            </p>
          </div>
        </section>

        <section className="border-y border-white/8 bg-white/[0.025] px-5 py-16 sm:px-8">
          <div className="mx-auto max-w-6xl">
            <div className="mb-10 max-w-2xl">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-azure">Da ideia ao MP4</p>
              <h2 className="mt-3 font-display text-3xl font-bold sm:text-4xl">Um fluxo simples, com espaço para editar</h2>
            </div>
            <div className="grid gap-5 md:grid-cols-3">
              {STEPS.map(([number, title, description]) => (
                <article key={number} className="rounded-2xl border border-white/10 bg-panel/80 p-6">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-coral/15 text-sm font-bold text-coral">
                    {number}
                  </span>
                  <h3 className="mt-5 text-xl font-bold">{title}</h3>
                  <p className="mt-2 leading-relaxed text-mist">{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="px-5 py-20 sm:px-8">
          <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-coral">Perguntas frequentes</p>
              <h2 className="mt-3 font-display text-3xl font-bold sm:text-4xl">A oferta, sem letras miúdas</h2>
              <p className="mt-4 leading-relaxed text-mist">
                A campanha não usa contagem regressiva nem disponibilidade artificial. As condições abaixo explicam
                quando e como o crédito é aplicado.
              </p>
            </div>
            <div className="space-y-4">
              {FAQ.map(([question, answer]) => (
                <details key={question} className="group rounded-2xl border border-white/10 bg-white/[0.035] p-5 open:bg-white/[0.055]">
                  <summary className="cursor-pointer list-none font-semibold text-cloud">{question}</summary>
                  <p className="mt-3 leading-relaxed text-mist">{answer}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="px-5 pb-20 sm:px-8">
          <div className="mx-auto max-w-4xl rounded-3xl border border-coral/25 bg-gradient-to-br from-coral/15 to-azure/10 p-8 text-center sm:p-12">
            <h2 className="font-display text-3xl font-bold sm:text-4xl">Sua próxima ideia pode virar vídeo</h2>
            <p className="mx-auto mt-3 max-w-xl text-mist">Crie a conta, confirme o e-mail e use os 20 créditos no seu ritmo.</p>
            <Button href={CAMPAIGN_CTA} size="lg" iconRight="arrowRight" className="mt-7">
              Criar com 20 créditos
            </Button>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/8 px-5 py-8 text-center text-sm text-mist-2">
        <Link href="/termos" className="hover:text-cloud">Termos de Uso</Link>
        <span className="mx-3">·</span>
        <Link href="/privacidade" className="hover:text-cloud">Política de Privacidade</Link>
      </footer>
    </div>
  );
}
