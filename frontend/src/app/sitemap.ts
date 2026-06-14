import type { MetadataRoute } from "next";
import { blogPosts } from "@/lib/blog-posts";
import { getAllNicheSlugs } from "@/lib/niches";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://clipia.com.br";

  const staticPages: MetadataRoute.Sitemap = [
    { url: base, changeFrequency: "daily", priority: 1 },
    { url: `${base}/exemplos`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/auth/login`, changeFrequency: "monthly", priority: 0.3 },
    { url: `${base}/auth/register`, changeFrequency: "monthly", priority: 0.5 },
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
