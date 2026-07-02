import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import DOMPurify from "isomorphic-dompurify";
import { blogPosts, getPostBySlug } from "@/lib/blog-posts";

export function generateStaticParams() {
  return blogPosts.map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<PageProps<"/blog/[slug]">["params"] extends Promise<infer P> ? P : never>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) return {};
  return {
    title: `${post.title} — ClipIA`,
    description: post.description,
    openGraph: {
      title: post.title,
      description: post.description,
      url: `https://clipia.com.br/blog/${post.slug}`,
      type: "article",
      publishedTime: post.date,
    },
  };
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<PageProps<"/blog/[slug]">["params"] extends Promise<infer P> ? P : never>;
}) {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) notFound();

  return (
    <div className="min-h-screen bg-[#0b0d15]">
      <article className="max-w-3xl mx-auto px-4 py-16">
        <Link
          href="/blog"
          className="text-sm text-coral hover:text-coral-soft transition mb-8 inline-block"
        >
          ← Voltar para o blog
        </Link>

        <time className="text-xs text-slate-500 font-mono">
          {new Date(post.date).toLocaleDateString("pt-BR", {
            day: "2-digit",
            month: "long",
            year: "numeric",
          })}
        </time>

        <h1 className="text-4xl font-bold text-white mt-3 mb-8 tracking-tight leading-tight">
          {post.title}
        </h1>

        <div className="prose prose-invert max-w-none text-slate-300 leading-relaxed [&_h2]:text-white [&_h2]:text-2xl [&_h2]:font-bold [&_h2]:mt-10 [&_h2]:mb-4 [&_h3]:text-white [&_h3]:text-lg [&_h3]:font-bold [&_h3]:mt-8 [&_h3]:mb-3 [&_p]:mb-4 [&_ul]:mb-4 [&_ul]:space-y-2 [&_li]:text-slate-300 [&_strong]:text-white [&_a]:text-coral [&_a]:underline hover:[&_a]:text-coral-soft">
          {post.content.split("\n").map((line, i) => {
            const trimmed = line.trim();
            if (!trimmed) return null;
            if (trimmed.startsWith("### "))
              return (
                <h3 key={i}>{trimmed.slice(4)}</h3>
              );
            if (trimmed.startsWith("## "))
              return (
                <h2 key={i}>{trimmed.slice(3)}</h2>
              );
            if (trimmed.startsWith("- **")) {
              const match = trimmed.match(/^- \*\*(.+?)\*\*:?\s*(.*)$/);
              if (match)
                return (
                  <p key={i}>
                    • <strong>{match[1]}</strong>
                    {match[2] ? `: ${match[2]}` : ""}
                  </p>
                );
            }
            if (trimmed.startsWith("- "))
              return <p key={i}>• {trimmed.slice(2)}</p>;
            if (trimmed.match(/^\d+\.\s/)) {
              return <p key={i}>{trimmed}</p>;
            }
            // Handle inline links
            const withLinks = trimmed.replace(
              /\[(.+?)\]\((.+?)\)/g,
              '<a href="$2">$1</a>'
            );
            if (withLinks !== trimmed) {
              return (
                <p
                  key={i}
                  dangerouslySetInnerHTML={{
                    __html: DOMPurify.sanitize(withLinks, {
                      ALLOWED_TAGS: ["a", "strong", "em", "p", "br", "ul", "ol", "li", "h2", "h3"],
                      ALLOWED_ATTR: ["href", "target", "rel"],
                    }),
                  }}
                />
              );
            }
            // Handle bold
            const withBold = trimmed.replace(
              /\*\*(.+?)\*\*/g,
              "<strong>$1</strong>"
            );
            if (withBold !== trimmed) {
              return (
                <p
                  key={i}
                  dangerouslySetInnerHTML={{
                    __html: DOMPurify.sanitize(withBold, {
                      ALLOWED_TAGS: ["a", "strong", "em", "p", "br", "ul", "ol", "li", "h2", "h3"],
                      ALLOWED_ATTR: ["href", "target", "rel"],
                    }),
                  }}
                />
              );
            }
            return <p key={i}>{trimmed}</p>;
          })}
        </div>

        <div className="mt-16 pt-8 border-t border-white/10">
          <div className="rounded-2xl bg-gradient-to-r from-coral/20 to-azure/20 border border-coral/20 p-8 text-center">
            <h2 className="text-2xl font-bold text-white mb-3">
              Pronto para criar seu primeiro vídeo?
            </h2>
            <p className="text-slate-400 mb-6">
              2 créditos grátis. Sem cartão de crédito.
            </p>
            <Link
              href="/auth/register"
              className="inline-block px-8 py-3.5 rounded-xl bg-gradient-to-r from-coral to-azure text-white font-bold hover:opacity-90 transition shadow-lg shadow-coral/25"
            >
              Criar conta grátis →
            </Link>
          </div>
        </div>
      </article>
    </div>
  );
}
