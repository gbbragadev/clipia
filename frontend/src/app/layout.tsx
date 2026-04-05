import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import FilmGrain from "@/components/FilmGrain";
import AppProviders from "@/components/providers/AppProviders";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "700"],
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${spaceGrotesk.variable} h-full antialiased`}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "SoftwareApplication",
              "name": "ClipIA",
              "applicationCategory": "MultimediaApplication",
              "operatingSystem": "Web",
              "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "BRL"
              },
              "description": "Plataforma de geração automatizada de vídeos curtos com IA",
              "url": "https://clipia.com.br"
            })
          }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        <FilmGrain />
        <AppProviders>
          {children}
        </AppProviders>
      </body>
    </html>
  );
}
