import type { NextConfig } from "next";

const backend = process.env.BACKEND_API_BASE ?? "http://127.0.0.1:8010";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/outputs/:path*",
        destination: `${backend}/outputs/:path*`,
      },
    ];
  },
};

export default nextConfig;
