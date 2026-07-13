import type { MetadataRoute } from "next";
import { blogPosts } from "@/lib/blog-posts";
import { getAllNicheSlugs } from "@/lib/niches";
import { SITE } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = SITE.url;

  // Auth fica fora do sitemap (páginas utilitárias, noindex no layout); o hub
  // /blog entra — os posts sem o hub ficavam órfãos de descoberta.
  const staticPages: MetadataRoute.Sitemap = [
    { url: base, changeFrequency: "daily", priority: 1 },
    { url: `${base}/exemplos`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/blog`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/suporte`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${base}/termos`, lastModified: "2026-07-02", changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/privacidade`, lastModified: "2026-07-02", changeFrequency: "yearly", priority: 0.3 },
  ];

  const nichePages: MetadataRoute.Sitemap = getAllNicheSlugs().map((slug) => ({
    url: `${base}/criar/${slug}`,
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  const blogPages: MetadataRoute.Sitemap = blogPosts.map((post) => ({
    url: `${base}/blog/${post.slug}`,
    lastModified: post.date,
    changeFrequency: "monthly" as const,
    priority: 0.7,
  }));

  return [...staticPages, ...nichePages, ...blogPages];
}
