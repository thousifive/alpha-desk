/// <reference types="vite-plugin-pwa/react" />

interface ImportMetaEnv {
  /** Backend origin for production builds, e.g. https://api.example.com. Unset in dev. */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
