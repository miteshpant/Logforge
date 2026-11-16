/** @type {import('next').NextConfig} */
const nextConfig = {
  // Self-contained server for the production Docker image (see Dockerfile).
  output: 'standalone',
  // App directory is now stable in Next.js 14 - no experimental flag needed
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