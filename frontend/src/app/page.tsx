import type { Metadata } from "next";
import { SkipLink } from "@/components/landing/SkipLink";
import { Nav } from "@/components/landing/Nav";
import { StickyCta } from "@/components/landing/StickyCta";
import { Hero } from "@/components/landing/sections/Hero";
import { BeforeAfter } from "@/components/landing/sections/BeforeAfter";
import { FactsBar } from "@/components/landing/sections/FactsBar";
import { Personas } from "@/components/landing/sections/Personas";
import { NichesGrid } from "@/components/landing/sections/NichesGrid";
import { HowItWorks } from "@/components/landing/sections/HowItWorks";
import { Pricing } from "@/components/landing/sections/Pricing";
import { FAQ } from "@/components/landing/sections/FAQ";
import { FinalCta } from "@/components/landing/sections/FinalCta";
import { Footer } from "@/components/landing/sections/Footer";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  alternates: { canonical: SITE.url },
};

// Anatomia de conversão: promessa concreta (Hero com vídeo real) → prova
// (antes→depois) → fatos verificáveis → chamada por persona → nichos/SEO →
// como funciona → preço transparente → FAQ honesta → CTA final.
export default function Home() {
  return (
    <div id="top" className="min-h-screen bg-ink text-cloud antialiased">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            name: "ClipIA",
            applicationCategory: "MultimediaApplication",
            operatingSystem: "Web",
            offers: { "@type": "Offer", price: "0", priceCurrency: "BRL" },
            description: "Plataforma de geração automatizada de vídeos curtos com IA",
            url: SITE.url,
          }),
        }}
      />
      <SkipLink />
      <Nav />
      <main id="conteudo">
        <Hero />
        <BeforeAfter />
        <FactsBar />
        <Personas />
        <NichesGrid />
        <HowItWorks />
        <Pricing />
        <FAQ />
        <FinalCta />
      </main>
      <Footer />
      <StickyCta />
    </div>
  );
}
