const path = require('path')

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Self-contained server for the production Docker image (see Dockerfile).
  output: 'standalone',
  // This app is its own root (the repo holds several lockfiles).
  outputFileTracingRoot: path.join(__dirname),
  // Nothing uses next/image.
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080',
    NEXT_PUBLIC_ADMIN_MODE: 'true'
  }
}

module.exports = nextConfig