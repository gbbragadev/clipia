import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";

import Logo from "@/components/brand/Logo";
import { FREE_CLAIM } from "@/components/landing/lib/data";
import { Button } from "@/components/landing/ui/Button";
import { JsonLd } from "@/components/StructuredData/JsonLd";
import { ApiError } from "@/lib/http";
import { getPublicShare } from "@/lib/public-shares";
import { buildShareJsonLd, buildShareMetadata, getShareDisplayTitle } from "@/lib/public-share-presentation";
import showcase from "../../../../public/showcase/showcase.json";
import QualifiedViewTracker from "./QualifiedViewTracker";

interface ShowcaseEntry {
  id: string;
  title: string;
  template: string;
  niche: string;
  video: string;
  poster?: string;
  published_at?: string;
}

interface ResolvedVideo extends ShowcaseEntry {
  kind: "showcase" | "public";
}

const VIDEOS: ShowcaseEntry[] = (showcase as { videos: ShowcaseEntry[] }).videos;

export function generateStaticParams() {
  return VIDEOS.map((video) => ({ id: video.id }));
}

const resolveVideo = cache(async (id: string): Promise<ResolvedVideo | null> => {
  // IDs editoriais continuam resolvidos pelo JSON local, sem depender da API.
  const showcaseVideo = VIDEOS.find((video) => video.id === id);
  if (showcaseVideo) return { ...showcaseVideo, kind: "showcase" };

  try {
    const publicShare = await getPublicShare(id);
    if (!publicShare.active) return null;
    return {
      id,
      // O topic livre do job não entra em metadata, JSON-LD nem markup público.
      title: "Vídeo publicado com ClipIA",
      template: "vídeo publicado",
      niche: "conteúdo de criador",
      // O navegador recebe apenas a rota pública; nenhum caminho de armazenamento é exposto.
      video: `/api/v1/public-shares/${encodeURIComponent(id)}/video`,
      published_at: publicShare.published_at,
      kind: "public",
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

export async function generateMetadata({
  params,
}: PageProps<"/v/[id]">): Promise<Metadata> {
  const { id } = await params;
  const video = await resolveVideo(id);
  if (!video) return {};
  return buildShareMetadata(video);
}

export default async function SharePage({ params }: PageProps<"/v/[id]">) {
  const { id } = await params;
  const video = await resolveVideo(id);
  if (!video) notFound();

  const cta = "/auth/register?utm_source=public_share&utm_medium=organic_social&utm_campaign=creator20_v1&utm_content=public_video";
  const isShowcase = video.kind === "showcase";
  const displayTitle = getShareDisplayTitle(video);

  return (
    <div className="flex min-h-screen flex-col bg-ink text-cloud antialiased">
      {!isShowcase && <QualifiedViewTracker token={video.id} />}
      <JsonLd data={buildShareJsonLd(video)} />
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
              <video
                src={video.video}
                poster={video.poster}
                controls
                playsInline
                preload="metadata"
                aria-label={displayTitle}
                className="absolute inset-0 h-full w-full object-cover"
              />
            </div>
          </div>
        </div>

        <h1 className="mt-6 max-w-md text-balance text-center text-2xl font-bold leading-tight">
          {displayTitle}
        </h1>
        <p className="mt-2 flex items-center gap-2 text-sm text-mist">
          <span className="h-1.5 w-1.5 rounded-full bg-coral" />
          {isShowcase ? `Feito com ClipIA · template ${video.template}` : "Publicado pelo criador com ClipIA"}
        </p>
        <p className="mt-1 text-center text-[13px] text-mist-2">
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
        <p className="mt-3 text-[13px] text-mist-2">{FREE_CLAIM}</p>
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
