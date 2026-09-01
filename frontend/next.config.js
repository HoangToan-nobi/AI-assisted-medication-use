const path = require("path");
const { loadEnvConfig } = require("@next/env");

// Local development keeps the shared backend/frontend settings in the root
// .env. Docker builds still receive public values through build arguments.
loadEnvConfig(path.resolve(__dirname, ".."));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // Backend waits up to 300 seconds for CPU OCR; keep the rewrite proxy alive
    // slightly longer so it can return the real result or timeout response.
    proxyTimeout: 310_000,
  },
  async rewrites() {
    const backend = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
      .trim()
      .replace(/\/+$/, "");
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
      ],
    }];
  },
};

module.exports = nextConfig;
