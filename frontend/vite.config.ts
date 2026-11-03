/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Same-origin API keeps the session cookie simple (no CORS, SameSite=Lax works).
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    // The lazy exercise chunk carries Monaco (~3 MB raw / ~0.8 MB gzip). It's only fetched on
    // the exercise route, so we accept it instead of warning on every build.
    chunkSizeWarningLimit: 3500,
  },
  test: {
    environment: 'jsdom',
  },
})
