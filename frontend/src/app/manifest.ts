import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ClipIA",
    short_name: "ClipIA",
    description:
      "Transforme qualquer tema em video pronto para publicar. Roteiro, narracao, legendas e edicao — tudo automatico com IA.",
    start_url: "/",
    display: "standalone",
    background_color: "#050509",
    theme_color: "#7c3aed",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
