import { SkipLink } from "@/components/landing/SkipLink";
import { Nav } from "@/components/landing/Nav";
import { StickyCta } from "@/components/landing/StickyCta";
import { Hero } from "@/components/landing/sections/Hero";
import { ValueProps } from "@/components/landing/sections/ValueProps";
import { InteractiveDemo } from "@/components/landing/sections/InteractiveDemo";
import { HowItWorks } from "@/components/landing/sections/HowItWorks";
import { Gallery } from "@/components/landing/sections/Gallery";
import { Differentials } from "@/components/landing/sections/Differentials";
import { ProductProof } from "@/components/landing/sections/ProductProof";
import { FAQ } from "@/components/landing/sections/FAQ";
import { FinalCta } from "@/components/landing/sections/FinalCta";
import { Footer } from "@/components/landing/sections/Footer";

export default function Home() {
  return (
    <div id="top" className="min-h-screen bg-ink text-cloud antialiased">
      <SkipLink />
      <Nav />
      <main id="conteudo">
        <Hero />
        <ValueProps />
        <InteractiveDemo />
        <HowItWorks />
        <Gallery />
        <Differentials />
        <ProductProof />
        <FAQ />
        <FinalCta />
      </main>
      <Footer />
      <StickyCta />
    </div>
  );
}
