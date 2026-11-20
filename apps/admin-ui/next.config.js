/** @type {import('next').NextConfig} */
const nextConfig = {
  // Self-contained server for the production Docker image (see Dockerfile).
  output: 'standalone',
  // Unused, and Next 14's image optimizer has unfixed advisories (security/audit-allowlist.json).
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080',
    NEXT_PUBLIC_ADMIN_MODE: 'true'
  }
}

module.exports = nextConfig