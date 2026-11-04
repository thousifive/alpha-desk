/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, searchForWorkspaceRoot } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Same-origin API keeps the session cookie simple (no CORS, SameSite=Lax works).
    proxy: { '/api': process.env.API_URL ?? 'http://127.0.0.1:8000' },
    // The Pyodide workers import backend Python as ?raw strings: the test harness, and the
    // pure rules modules for the local rules worker. Allow backend/app (never backend/.env).
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), '../backend/app'] },
  },
  build: {
    // The lazy exercise chunk carries Monaco (~3 MB raw / ~0.8 MB gzip). It's only fetched on
    // the exercise route, so we accept it instead of warning on every build.
    chunkSizeWarningLimit: 3500,
  },
  worker: { format: 'es' }, // module worker: it uses dynamic import() for the Pyodide loader
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
  },
})
