import { SITE } from "@/lib/site";

export interface ArticleLinkProps {
  target?: "_blank";
  rel?: "noopener noreferrer";
}

const SITE_ORIGIN = new URL(SITE.url).origin;

export function getArticleLinkProps(href?: string): ArticleLinkProps {
  if (!href) return {};

  try {
    const destination = new URL(href, SITE.url);
    const isHttp = destination.protocol === "http:" || destination.protocol === "https:";
    if (isHttp && destination.origin !== SITE_ORIGIN) {
      return { target: "_blank", rel: "noopener noreferrer" };
    }
  } catch {
    // O react-markdown descarta protocolos inseguros; props extras não são necessárias.
  }

  return {};
}
