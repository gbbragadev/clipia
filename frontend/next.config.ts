import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Build de verificação isolado: NEXT_DIST_DIR permite buildar/prever mudanças
  // sem tocar o .next servido em produção (bug raiz documentado em
  // scripts/restart-frontend.ps1 — rebuild in-place derruba o next start vivo).
  distDir: process.env.NEXT_DIST_DIR || ".next",
  allowedDevOrigins: ["autoshorts.gbbragadev.com", "clipia.com.br", "www.clipia.com.br"],
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "www\\.clipia\\.com\\.br" }],
        destination: "https://clipia.com.br/:path*",
        permanent: true,
      },
    ];
  },
  async headers() {
    // Headers de seguranca espelham a politica do backend (app/main.py) + anti-clickjacking.
    // CSP usa apenas frame-ancestors para nao quebrar os scripts/styles inline do Next/Remotion.
    const securityHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "X-XSS-Protection", value: "1; mode=block" },
      { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
    ];
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=0, s-maxage=0, must-revalidate",
          },
          ...securityHeaders,
        ],
      },
    ];
  },
  async rewrites() {
    // 127.0.0.1 (não localhost): o uvicorn escuta só IPv4 e o resolver desta máquina
    // às vezes tenta ::1 primeiro → 500 intermitente no proxy (visto no audit 11/07).
    const apiUrl = process.env.LOCAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8005";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
      {
        source: "/storage/:path*",
        destination: `${apiUrl}/storage/:path*`,
      },
      // Health do backend exposto externamente para monitoracao (UptimeRobot, etc.).
      // O backend serve /health e /health/deep na raiz; o Next precisa repassar para
      // um monitor externo conseguir bater sem conhecer a porta interna 8005.
      {
        source: "/health",
        destination: `${apiUrl}/health`,
      },
      {
        source: "/health/:path*",
        destination: `${apiUrl}/health/:path*`,
      },
    ];
  },
};

export default nextConfig;
