const path = require('path')

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Self-contained server for the production Docker image (see Dockerfile).
  output: 'standalone',
  // This app is its own root (the repo holds several lockfiles).
  outputFileTracingRoot: path.join(__dirname),
  // Nothing uses next/image.
  images: { unoptimized: true },
  typescript: {
    // Allow production builds to succeed even if there are type errors
    ignoreBuildErrors: false,
  },
  eslint: {
    // Allow production builds to succeed even if there are ESLint errors
    ignoreDuringBuilds: false,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:7080',
  },
}

module.exports = nextConfig