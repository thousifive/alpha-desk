/// <reference types="vite-plugin-pwa/react" />

interface ImportMetaEnv {
  /** Backend origin for production builds: the tailnet URL, e.g. https://alpha-desk.<tailnet>.ts.net. Unset in dev. */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
