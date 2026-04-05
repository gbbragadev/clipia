import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ClipIA",
    short_name: "ClipIA",
    description:
      "Transforme qualquer tema em vídeo pronto para publicar. Roteiro, narração, legendas e edição — tudo automático com IA.",
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
