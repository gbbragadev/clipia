import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Logo from "@/components/brand/Logo";
import { Button } from "@/components/landing/ui/Button";
import showcase from "../../../../public/showcase/showcase.json";
import { FREE_CLAIM } from "@/components/landing/lib/data";

// Página pública de compartilhamento (loop viral): vídeo + "crie o seu".
// Hoje serve os vídeos do showcase; vídeos de usuário entram quando existir
// endpoint público opt-in no backend (decisão de produto pendente).

interface ShowcaseEntry {
  id: string;
  title: string;
  template: string;
  niche: string;
  video: string;
  poster?: string;
}

const VIDEOS: ShowcaseEntry[] = (showcase as { videos: ShowcaseEntry[] }).videos;

export const dynamicParams = false;

export function generateStaticParams() {
  return VIDEOS.map((v) => ({ id: v.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const v = VIDEOS.find((x) => x.id === id);
  if (!v) return {};
  const title = `${v.title} — feito com ClipIA`;
  const description =
    "Vídeo vertical gerado e editado no ClipIA: roteiro, narração em português e legendas sincronizadas. Crie o seu grátis.";
  // No Next 16 a metadata mescla por chave de topo: redefinir openGraph SUBSTITUI o
  // objeto global inteiro — sem images aqui, o WhatsApp mostrava card SEM imagem.
  const ogImage = `https://clipia.com.br/showcase/og/${v.id}.jpg`;
  return {
    title,
    description,
    alternates: { canonical: `https://clipia.com.br/v/${v.id}` },
    openGraph: {
      title,
      description,
      type: "video.other",
      url: `https://clipia.com.br/v/${v.id}`,
      siteName: "ClipIA",
      locale: "pt_BR",
      images: [{ url: ogImage, width: 1200, height: 630, alt: v.title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImage],
    },
  };
}

export default async function SharePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const v = VIDEOS.find((x) => x.id === id);
  if (!v) notFound();

  const cta = `/auth/register?utm_source=share&utm_medium=organic&utm_campaign=v-page&utm_content=${v.id}`;

  return (
    <div className="flex min-h-screen flex-col bg-ink text-cloud antialiased">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "VideoObject",
            name: v.title,
            description: `Vídeo vertical de ${v.niche} gerado e editado no ClipIA (template ${v.template}).`,
            thumbnailUrl: `https://clipia.com.br/showcase/og/${v.id}.jpg`,
            contentUrl: `https://clipia.com.br${v.video}`,
            // Data de publicação do showcase atual (arquivos de 04/2026).
            uploadDate: "2026-04-04",
            inLanguage: "pt-BR",
          }),
        }}
      />
      <header className="flex items-center justify-between px-5 py-4 sm:px-8">
        <Link href="/" aria-label="ClipIA — início">
          <Logo />
        </Link>
        <Button href={cta} size="sm" iconRight="arrowRight">
          Criar vídeo grátis
        </Button>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center px-5 py-8">
        <div className="w-full max-w-[320px]">
          <div className="rounded-[2.4rem] border border-white/12 bg-panel/90 p-2 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.9)]">
            <div className="relative aspect-[9/16] overflow-hidden rounded-[1.9rem] bg-ink">
              {/* controles nativos: página de share precisa de play/pause/som simples */}
              <video
                src={v.video}
                poster={v.poster}
                controls
                playsInline
                preload="metadata"
                aria-label={v.title}
                className="absolute inset-0 h-full w-full object-cover"
              />
            </div>
          </div>
        </div>

        <h1 className="mt-6 max-w-md text-balance text-center text-2xl font-bold leading-tight">
          {v.title}
        </h1>
        <p className="mt-2 flex items-center gap-2 text-sm text-mist">
          <span className="h-1.5 w-1.5 rounded-full bg-coral" />
          Feito com ClipIA · template {v.template}
        </p>
        <p className="mt-1 text-[13px] text-mist-2">
          Roteiro, narração em português e legendas — gerados e editados na plataforma.
        </p>

        <div className="mt-7 flex flex-col items-center gap-3 sm:flex-row">
          <Button href={cta} size="lg" iconRight="arrowRight">
            Crie o seu grátis
          </Button>
          <Button href="/exemplos" variant="secondary" size="lg">
            Ver mais exemplos
          </Button>
        </div>
        <p className="mt-3 text-[13px] text-mist-2">
          {FREE_CLAIM}
        </p>
      </main>

      <footer className="px-5 py-6 text-center text-[12px] text-mist-2">
        © {new Date().getFullYear()} ClipIA ·{" "}
        <Link href="/termos" className="underline decoration-white/20 underline-offset-4 hover:text-cloud">
          Termos
        </Link>{" "}
        ·{" "}
        <Link href="/privacidade" className="underline decoration-white/20 underline-offset-4 hover:text-cloud">
          Privacidade
        </Link>
      </footer>
    </div>
  );
}
