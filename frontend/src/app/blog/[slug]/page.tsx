import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { JsonLd } from "@/components/StructuredData/JsonLd";
import { blogPosts, getPostBySlug } from "@/lib/blog-posts";
import { getArticleLinkProps } from "@/lib/markdown-links";
import { canonicalUrl, SITE } from "@/lib/site";

const ARTICLE_ELEMENTS = [
  "h2",
  "h3",
  "p",
  "ul",
  "ol",
  "li",
  "strong",
  "em",
  "a",
  "blockquote",
  "code",
  "pre",
  "hr",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "del",
  "input",
] as const;

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
  const url = canonicalUrl(`/blog/${post.slug}`);
  return {
    title: `${post.title} — ClipIA`,
    description: post.description,
    alternates: { canonical: url },
    openGraph: {
      title: post.title,
      description: post.description,
      url,
      type: "article",
      publishedTime: post.date,
      images: [{ url: "/og-image.png", width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.description,
      images: ["/og-image.png"],
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
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "BlogPosting",
          headline: post.title,
          description: post.description,
          datePublished: post.date,
          inLanguage: "pt-BR",
          mainEntityOfPage: canonicalUrl(`/blog/${post.slug}`),
          author: { "@type": "Organization", name: SITE.name, url: SITE.url },
          publisher: { "@type": "Organization", name: SITE.name, url: SITE.url },
        }}
      />
      <article className="max-w-3xl mx-auto px-4 py-16">
        <Link
          href="/blog"
          className="text-sm text-coral hover:text-coral-soft transition mb-8 inline-block"
        >
          ← Voltar para o blog
        </Link>

        <time dateTime={post.date} className="text-xs text-slate-500 font-mono">
          {new Date(post.date).toLocaleDateString("pt-BR", {
            day: "2-digit",
            month: "long",
            year: "numeric",
            timeZone: "UTC",
          })}
        </time>

        <h1 className="text-4xl font-bold text-white mt-3 mb-8 tracking-tight leading-tight">
          {post.title}
        </h1>

        <div className="prose prose-invert max-w-none text-slate-300 leading-relaxed [&_h2]:text-white [&_h2]:text-2xl [&_h2]:font-bold [&_h2]:mt-10 [&_h2]:mb-4 [&_h3]:text-white [&_h3]:text-lg [&_h3]:font-bold [&_h3]:mt-8 [&_h3]:mb-3 [&_p]:mb-4 [&_ul]:mb-4 [&_ul]:space-y-2 [&_li]:text-slate-300 [&_strong]:text-white [&_a]:text-coral [&_a]:underline hover:[&_a]:text-coral-soft">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            allowedElements={[...ARTICLE_ELEMENTS]}
            skipHtml
            components={{
              a: ({ href, children, node: _node, ...props }) => {
                return (
                  <a
                    {...props}
                    href={href}
                    {...getArticleLinkProps(href)}
                  >
                    {children}
                  </a>
                );
              },
            }}
          >
            {post.content}
          </ReactMarkdown>
        </div>

        <div className="mt-16 pt-8 border-t border-white/10">
          <div className="rounded-2xl bg-gradient-to-r from-coral/20 to-azure/20 border border-coral/20 p-8 text-center">
            <h2 className="text-2xl font-bold text-white mb-3">
              Pronto para criar seu primeiro vídeo?
            </h2>
            <p className="text-slate-400 mb-6">
              Créditos grátis de boas-vindas. Sem cartão de crédito.
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
