import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { Sora } from "next/font/google";
import "./globals.css";
import FilmGrain from "@/components/FilmGrain";
import AppProviders from "@/components/providers/AppProviders";
import TrackingScripts from "@/components/TrackingScripts";

// Sora = display (titulos cinematograficos); GeistSans = corpo (var --font-geist-sans).
const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "ClipIA - Crie vídeos curtos com IA",
  description:
    "Transforme qualquer tema em vídeo pronto para publicar. Roteiro, narração, legendas e edição — tudo automático com IA.",
  icons: {
    icon: [
      { url: "/favicon-icon.svg", type: "image/svg+xml" },
    ],
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "ClipIA - Crie vídeos curtos com IA",
    description:
      "Transforme qualquer tema em vídeo pronto para publicar. Roteiro, narração, legendas e edição — tudo automático com IA.",
    url: "https://clipia.com.br",
    siteName: "ClipIA",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "ClipIA — Crie videos curtos com IA",
      },
    ],
    locale: "pt_BR",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "ClipIA - Crie videos curtos com IA",
    description:
      "Transforme qualquer tema em video pronto para publicar com IA.",
    images: ["/og-image.png"],
  },
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_BASE_URL || "https://clipia.com.br"
  ),
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover", // habilita env(safe-area-inset-*) p/ notch (editor + barras)
  themeColor: "#0a0a12",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={`h-full antialiased ${GeistSans.variable} ${sora.variable}`}>
      {/* JSON-LD de SoftwareApplication vive na home (app/page.tsx) — em artigo,
          auth e viewer o schema global confundia parsers (rich results imprecisos). */}
      <body className="min-h-full flex flex-col">
        <TrackingScripts />
        <FilmGrain />
        <AppProviders>
          {children}
        </AppProviders>
      </body>
    </html>
  );
}
