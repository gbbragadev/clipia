import type { Metadata } from "next";
import Link from "next/link";
import { blogPosts } from "@/lib/blog-posts";

export const metadata: Metadata = {
  title: "Blog — ClipIA",
  description:
    "Dicas, tutoriais e novidades sobre criação de vídeos curtos com IA. Shorts, Reels e TikTok automáticos.",
  openGraph: {
    title: "Blog — ClipIA",
    description: "Dicas e tutoriais sobre vídeos curtos com IA",
    url: "https://clipia.com.br/blog",
  },
};

export default function BlogPage(_props: PageProps<"/blog">) {
  return (
    <div className="min-h-screen bg-[#0b0d15]">
      <div className="max-w-3xl mx-auto px-4 py-16">
        <Link
          href="/"
          className="text-sm text-coral hover:text-coral-soft transition mb-8 inline-block"
        >
          ← Voltar para o início
        </Link>

        <h1 className="text-4xl font-bold text-white mb-3 tracking-tight">
          Blog
        </h1>
        <p className="text-slate-400 text-lg mb-12">
          Dicas, tutoriais e novidades sobre criação de vídeos com IA.
        </p>

        <div className="space-y-8">
          {blogPosts.map((post) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="block group rounded-2xl bg-white/[0.03] border border-white/5 p-6 hover:bg-white/[0.06] hover:border-coral/20 transition-all"
            >
              <time className="text-xs text-slate-500 font-mono">
                {new Date(post.date).toLocaleDateString("pt-BR", {
                  day: "2-digit",
                  month: "long",
                  year: "numeric",
                })}
              </time>
              <h2 className="text-xl font-bold text-white mt-2 mb-2 group-hover:text-coral-soft transition">
                {post.title}
              </h2>
              <p className="text-slate-400 text-sm leading-relaxed">
                {post.description}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
