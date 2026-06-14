import type { Metadata } from "next";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import ShowcaseSection from "@/components/ShowcaseSection";
import { CinematicSection } from "@/components/ui/CinematicSection";
import { NICHES } from "@/lib/niches";

const BASE = "https://clipia.com.br";

export const metadata: Metadata = {
  title: "Exemplos de Vídeos Criados com IA por Nicho | ClipIA",
  description:
    "Veja exemplos de vídeos criados com o ClipIA: curiosidades, conteúdo religioso, motivacional, finanças, histórias, humor e drama histórico. Escolha seu nicho.",
  alternates: { canonical: `${BASE}/exemplos` },
  openGraph: {
    title: "Exemplos de Vídeos Criados com IA por Nicho | ClipIA",
    description: "Escolha um nicho e veja vídeos reais gerados no ClipIA.",
    url: `${BASE}/exemplos`,
    type: "website",
  },
};

export default function ExemplosPage() {
  return (
    <div className="min-h-screen bg-[#0f0b1a]">
      <Navbar />

      <main className="pt-16">
        <CinematicSection background="mesh" spacing="xl" reveal="fade-up">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl md:text-5xl font-bold text-white tracking-tight">
              Crie vídeos para o seu nicho
            </h1>
            <p className="mt-4 text-lg text-slate-300">
              Escolha um tema e veja o que a IA cria em minutos — roteiro, narração em português,
              legendas e mídia, prontos para Shorts, Reels e TikTok.
            </p>
          </div>

          {/* Grid de nichos (hub de internal linking) */}
          <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 gap-5 max-w-5xl mx-auto">
            {NICHES.map((n) => (
              <Link
                key={n.slug}
                href={`/criar/${n.slug}`}
                className={`group rounded-2xl bg-gradient-to-br ${n.gradient} border border-white/10 p-6 hover:border-white/25 transition-all`}
              >
                <div className="text-4xl mb-3" aria-hidden>{n.emoji}</div>
                <h2 className="text-lg font-bold text-white">{n.label}</h2>
                <p className="mt-1.5 text-sm text-slate-300">{n.heroSubtitle}</p>
                <span
                  className="inline-block mt-4 text-sm font-semibold group-hover:translate-x-1 transition-transform"
                  style={{ color: n.accent }}
                >
                  Criar vídeos de {n.label.toLowerCase()} →
                </span>
              </Link>
            ))}
          </div>
        </CinematicSection>

        {/* Galeria filtrável reaproveitada da home */}
        <ShowcaseSection />
      </main>

      <Footer />
    </div>
  );
}
