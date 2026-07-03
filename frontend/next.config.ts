import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["autoshorts.gbbragadev.com", "clipia.com.br", "www.clipia.com.br"],
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
    const apiUrl = process.env.LOCAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8005";
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
