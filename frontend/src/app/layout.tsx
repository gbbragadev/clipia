import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import FilmGrain from "@/components/FilmGrain";
import { AuthProvider } from "@/contexts/AuthContext";

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
  title: "ClipIA - Crie videos curtos com IA",
  description:
    "Transforme qualquer tema em video pronto para publicar. Roteiro, narracao, legendas e edicao — tudo automatico com IA.",
  icons: {
    icon: [
      { url: "/favicon-icon.svg", type: "image/svg+xml" },
    ],
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "ClipIA - Crie videos curtos com IA",
    description:
      "Transforme qualquer tema em video pronto para publicar. Roteiro, narracao, legendas e edicao — tudo automatico com IA.",
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
      <body className="min-h-full flex flex-col">
        <FilmGrain />
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
