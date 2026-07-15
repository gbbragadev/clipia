import type { NextConfig } from "next";

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://images.pexels.com",
  "font-src 'self' data:",
  // O Remotion Player usa um MP3 data: mínimo para sincronizar playback no browser.
  "media-src 'self' data: blob: https:",
  "connect-src 'self' https://challenges.cloudflare.com",
  "frame-src https://challenges.cloudflare.com",
  "worker-src 'self' blob:",
].join("; ");

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
    // Next e Remotion exigem bootstrap/style inline; todas as demais origens sao
    // fechadas, exceto os assets e o Turnstile usados pelo produto.
    const securityHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "X-XSS-Protection", value: "0" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      { key: "Content-Security-Policy", value: contentSecurityPolicy },
    ];
    if (process.env.NODE_ENV === "production") {
      securityHeaders.push({
        key: "Strict-Transport-Security",
        value: "max-age=31536000; includeSubDomains",
      });
    }
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
