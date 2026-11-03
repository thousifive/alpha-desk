/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, searchForWorkspaceRoot } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Same-origin API keeps the session cookie simple (no CORS, SameSite=Lax works).
    proxy: { '/api': process.env.API_URL ?? 'http://127.0.0.1:8000' },
    // The Pyodide worker imports backend/app/pyrunner/harness.py?raw (one harness for browser
    // and backend tests). Allow exactly that directory outside the frontend root.
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), '../backend/app/pyrunner'] },
  },
  build: {
    // The lazy exercise chunk carries Monaco (~3 MB raw / ~0.8 MB gzip). It's only fetched on
    // the exercise route, so we accept it instead of warning on every build.
    chunkSizeWarningLimit: 3500,
  },
  worker: { format: 'es' }, // module worker: it uses dynamic import() for the Pyodide loader
  test: {
    environment: 'jsdom',
  },
})
