export const SITE = {
  name: "ClipIA",
  url: "https://clipia.com.br",
} as const;

export function canonicalUrl(path = ""): string {
  if (!path || path === "/") return SITE.url;
  return `${SITE.url}${path.startsWith("/") ? path : `/${path}`}`;
}
