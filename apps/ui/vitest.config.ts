import { defineConfig } from 'vitest/config'
import path from 'path'

// Unit tests (Playwright end-to-end specs live in tests/ and are not run here).
export default defineConfig({
  test: {
    include: ['lib/**/*.test.ts', 'components/**/*.test.ts', 'app/**/*.test.ts'],
    environment: 'node',
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
})
