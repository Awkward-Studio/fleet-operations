import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname),
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/admin/:path*",
        destination: "http://127.0.0.1:8000/admin/:path*",
      },
      {
        source: "/static/admin/:path*",
        destination: "http://127.0.0.1:8000/static/admin/:path*",
      },
    ];
  },
};

export default nextConfig;
