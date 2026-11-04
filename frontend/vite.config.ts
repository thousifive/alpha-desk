/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, searchForWorkspaceRoot } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// A Netlify build without the API origin would deploy an app that can never reach the server
// (and still spend the deploy's credits). Fail the build instead.
if (process.env.NETLIFY === 'true' && !process.env.VITE_API_URL) {
  throw new Error(
    'VITE_API_URL is not set: add it in Netlify → Site configuration → Environment variables',
  )
}

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // 'prompt': a new version waits until the player taps the toast. Never reload mid-exercise.
      registerType: 'prompt',
      includeAssets: ['favicon.svg', 'apple-touch-icon.png'],
      manifest: {
        name: 'Alpha Desk',
        short_name: 'Alpha Desk',
        description: 'Meridian Capital trading-desk training game.',
        theme_color: '#07090c',
        background_color: '#07090c',
        display: 'standalone',
        orientation: 'any',
        start_url: '/',
        icons: [
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'pwa-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // App shell: every JS/CSS chunk (Monaco included, so exercises open offline) + HTML.
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // Pyodide runtime + wheels (pydantic) from the versioned CDN path. A versioned path
            // never changes, so cache forever after first use. A RegExp, not a closure:
            // Workbox stringifies matchers into sw.js, so outside variables would vanish.
            urlPattern: /^https:\/\/cdn\.jsdelivr\.net\/pyodide\/v[\d.]+\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'pyodide',
              cacheableResponse: { statuses: [200] },
              expiration: { maxEntries: 80 },
            },
          },
          {
            // DuckDB-WASM at an exact npm version on jsDelivr (src/lib/duckdb/cdn.ts): the
            // path never changes content, so cache forever. Only the build a device uses
            // (eh or mvp, ~36-41 MB) is ever fetched.
            urlPattern: /^https:\/\/cdn\.jsdelivr\.net\/npm\/@duckdb\/duckdb-wasm@[^/]+\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'duckdb',
              cacheableResponse: { statuses: [200] },
              expiration: { maxEntries: 6 },
            },
          },
          {
            // DuckDB autoloads its parquet extension from here on first read_parquet(). The
            // path carries the DuckDB version, so entries never change. Without this rule
            // offline SQL only worked while the HTTP cache happened to still hold the file.
            urlPattern: /^https:\/\/extensions\.duckdb\.org\/v[\d.]+\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'duckdb-extensions',
              cacheableResponse: { statuses: [200] },
              expiration: { maxEntries: 10 },
            },
          },
          {
            // Parquet files carry ?v=<dataset version>, so a regenerated dataset is a new URL.
            // Matched by path because the API is on another origin in production.
            urlPattern: ({ url }) => url.pathname.startsWith('/api/datasets/'),
            handler: 'CacheFirst',
            options: {
              cacheName: 'dataset',
              cacheableResponse: { statuses: [200] },
              expiration: { maxEntries: 24 },
            },
          },
        ],
      },
    }),
  ],
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
