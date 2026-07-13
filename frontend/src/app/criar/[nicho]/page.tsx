import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { NicheGallery } from "@/components/NicheGallery";
import { NicheFAQSchema } from "@/components/StructuredData/NicheFAQSchema";
import { BreadcrumbSchema } from "@/components/StructuredData/BreadcrumbSchema";
import { CinematicSection } from "@/components/ui/CinematicSection";
import { GlowCard } from "@/components/ui/GlowCard";
import { getAllNicheSlugs, getNicheBySlug } from "@/lib/niches";
import { getShowcaseVideosForNiche } from "@/lib/showcase";
import { FREE_CLAIM } from "@/components/landing/lib/data";

const BASE = "https://clipia.com.br";

function ctaHref(slug: string): string {
  return `/auth/register?utm_source=seo&utm_medium=organic&utm_campaign=nicho-${slug}`;
}

export function generateStaticParams() {
  return getAllNicheSlugs().map((nicho) => ({ nicho }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ nicho: string }>;
}): Promise<Metadata> {
  const { nicho } = await params;
  const n = getNicheBySlug(nicho);
  if (!n) return {};
  const url = `${BASE}/criar/${n.slug}`;
  return {
    title: n.metaTitle,
    description: n.metaDescription,
    alternates: { canonical: url },
    openGraph: {
      title: n.metaTitle,
      description: n.metaDescription,
      url,
      type: "website",
    },
  };
}

export default async function NichoPage({
  params,
}: {
  params: Promise<{ nicho: string }>;
}) {
  const { nicho } = await params;
  const n = getNicheBySlug(nicho);
  if (!n) notFound();
  const videos = getShowcaseVideosForNiche(n.slug);

  return (
    <div className="min-h-screen bg-[#0b0d15]">
      <Navbar />

      <main className="pt-16">
        {/* Hero */}
        <CinematicSection background="mesh" spacing="xl" reveal="fade-up">
          <div className={`mx-auto max-w-3xl text-center rounded-3xl bg-gradient-to-b ${n.gradient} p-8 md:p-12 border border-white/10`}>
            <div className="text-5xl sm:text-6xl mb-6" aria-hidden>{n.emoji}</div>
            <h1 className="text-4xl md:text-5xl font-bold text-white leading-tight tracking-tight">
              {n.h1}
            </h1>
            <p className="mt-4 text-lg md:text-xl text-slate-300">{n.heroSubtitle}</p>
            <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
              <Link
                href={ctaHref(n.slug)}
                className="inline-block px-8 py-3.5 rounded-xl bg-gradient-to-r from-coral to-azure text-white font-bold hover:opacity-90 transition shadow-lg shadow-coral/25"
              >
                Criar meu vídeo grátis →
              </Link>
              <Link
                href="/exemplos"
                className="inline-block px-8 py-3.5 rounded-xl bg-white/5 text-white/80 font-semibold border border-white/10 hover:bg-white/10 transition"
              >
                Ver mais exemplos
              </Link>
            </div>
            <p className="mt-3 text-xs text-slate-400">{FREE_CLAIM}</p>
          </div>
        </CinematicSection>

        {/* Galeria de exemplos (some se o nicho ainda nao tiver video) */}
        <CinematicSection background="none" spacing="lg" reveal="fade-up" className="border-t border-white/5">
          <div className="text-center mb-10 max-w-3xl mx-auto">
            <h2 className="text-2xl md:text-3xl font-bold text-white">
              Exemplos de {n.label.toLowerCase()} criados no ClipIA
            </h2>
            <p className="mt-3 text-slate-400">Vídeos reais gerados e editados na plataforma. Passe o mouse para ouvir.</p>
          </div>
          <NicheGallery videos={videos} />
        </CinematicSection>

        {/* Texto SEO (intro) */}
        <CinematicSection background="none" spacing="lg" className="border-t border-white/5">
          <div className="max-w-3xl mx-auto text-slate-300 leading-relaxed space-y-4 text-lg">
            {n.intro.split("\n\n").map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        </CinematicSection>

        {/* Benefits */}
        <CinematicSection background="none" spacing="lg" reveal="fade-up" className="border-t border-white/5">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-10">
              Por que usar o ClipIA para {n.label.toLowerCase()}
            </h2>
            <div className="grid sm:grid-cols-2 gap-5">
              {n.benefits.map((b) => (
                <GlowCard key={b.title} glowColor={n.accent} className="p-6">
                  <h3 className="text-lg font-bold text-white mb-2">{b.title}</h3>
                  <p className="text-slate-400">{b.description}</p>
                </GlowCard>
              ))}
            </div>
          </div>
        </CinematicSection>

        {/* Como funciona */}
        <CinematicSection background="none" spacing="lg" className="border-t border-white/5">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-10">
              Como criar vídeos de {n.label.toLowerCase()} em minutos
            </h2>
            <ol className="space-y-5">
              {n.howItWorks.map((s) => (
                <li key={s.step} className="flex gap-4">
                  <span
                    className="shrink-0 w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm text-white"
                    style={{ background: n.accent }}
                  >
                    {s.step}
                  </span>
                  <div>
                    <h3 className="text-white font-semibold">{s.title}</h3>
                    <p className="text-slate-400 mt-0.5">{s.description}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </CinematicSection>

        {/* Ideias de temas */}
        <CinematicSection background="none" spacing="lg" reveal="fade-up" className="border-t border-white/5">
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-2xl md:text-3xl font-bold text-white mb-3">
              Ideias de temas para vídeos de {n.label.toLowerCase()}
            </h2>
            <p className="text-slate-400 mb-8">Inspiração para começar agora mesmo.</p>
            <div className="flex flex-wrap gap-3 justify-center">
              {n.exampleTopics.map((t) => (
                <span
                  key={t}
                  className="text-sm px-4 py-2 rounded-full bg-white/5 text-white/80 border border-white/10"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        </CinematicSection>

        {/* FAQ */}
        <CinematicSection background="none" spacing="lg" className="border-t border-white/5">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-10">
              Perguntas frequentes
            </h2>
            <div className="space-y-3">
              {n.faqs.map((f) => (
                <details
                  key={f.question}
                  className="group rounded-xl bg-white/5 border border-white/10 p-5"
                >
                  <summary className="cursor-pointer text-white font-semibold list-none flex justify-between items-center gap-4">
                    {f.question}
                    <span className="text-slate-500 group-open:rotate-45 transition-transform">+</span>
                  </summary>
                  <p className="mt-3 text-slate-400 leading-relaxed">{f.answer}</p>
                </details>
              ))}
            </div>
          </div>
        </CinematicSection>

        {/* CTA final */}
        <CinematicSection background="none" spacing="lg" className="border-t border-white/5">
          <div className="max-w-3xl mx-auto">
            <div className="rounded-2xl bg-gradient-to-r from-coral/20 to-azure/20 border border-coral/20 p-8 md:p-10 text-center">
              <h2 className="text-2xl md:text-3xl font-bold text-white mb-3">
                Pronto para criar seu vídeo de {n.label.toLowerCase()}?
              </h2>
              <p className="text-slate-400 mb-6">{FREE_CLAIM}</p>
              <Link
                href={ctaHref(n.slug)}
                className="inline-block px-8 py-3.5 rounded-xl bg-gradient-to-r from-coral to-azure text-white font-bold hover:opacity-90 transition shadow-lg shadow-coral/25"
              >
                Criar conta grátis →
              </Link>
            </div>
          </div>
        </CinematicSection>
      </main>

      <Footer />

      <NicheFAQSchema niche={n} />
      <BreadcrumbSchema
        items={[
          { name: "Início", url: BASE },
          { name: "Exemplos", url: `${BASE}/exemplos` },
          { name: n.label, url: `${BASE}/criar/${n.slug}` },
        ]}
      />
    </div>
  );
}
