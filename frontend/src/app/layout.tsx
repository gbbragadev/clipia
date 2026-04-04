import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import FilmGrain from "@/components/FilmGrain";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ClipIA - Crie videos curtos com IA",
  description:
    "Transforme qualquer tema em video pronto para publicar. Roteiro, narracao, legendas e edicao — tudo automatico com IA.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <FilmGrain />
        {children}
      </body>
    </html>
  );
}
