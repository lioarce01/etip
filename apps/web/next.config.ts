import type { NextConfig } from "next";

// Server-side URL used by the Next.js proxy — never exposed to the browser.
// Local dev: http://localhost:8000 (default)
// Docker:    http://api:8000 (passed as INTERNAL_API_URL build arg)
const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      // All /auth/* and /api/v1/* browser requests are proxied server-side.
      // The browser sees same-origin calls → no CORS, cookies work naturally.
      {
        source: "/auth/:path*",
        destination: `${INTERNAL_API_URL}/auth/:path*`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${INTERNAL_API_URL}/api/v1/:path*`,
      },
      {
        source: "/tenants/:path*",
        destination: `${INTERNAL_API_URL}/tenants/:path*`,
      },
    ];
  },
};

export default nextConfig;
