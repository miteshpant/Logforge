/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080',
    NEXT_PUBLIC_ADMIN_MODE: 'true'
  }
}

module.exports = nextConfig