// DuckDB-WASM loads from jsDelivr at the exact npm version we build against, not from our
// own host: its .wasm files are 36-41 MB each, which Netlify's CDN handles poorly and which
// would count against the free plan's bandwidth credits on every new device.
export const DUCKDB_VERSION = '1.33.1-dev57.0' // keep equal to package.json (checked in a test)
export const DUCKDB_CDN = `https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@${DUCKDB_VERSION}/dist/`

export const DUCKDB_BUNDLES = {
  mvp: {
    mainModule: `${DUCKDB_CDN}duckdb-mvp.wasm`,
    mainWorker: `${DUCKDB_CDN}duckdb-browser-mvp.worker.js`,
  },
  eh: {
    mainModule: `${DUCKDB_CDN}duckdb-eh.wasm`,
    mainWorker: `${DUCKDB_CDN}duckdb-browser-eh.worker.js`,
  },
}

/**
 * Browsers refuse `new Worker(url)` for a cross-origin script, so we fetch the script and
 * start the worker from a same-origin blob. Fetching on the main thread (instead of a blob
 * that importScripts() the CDN URL) matters offline: this request goes through our service
 * worker and its cache, while a blob worker's importScripts would bypass it.
 */
export async function crossOriginWorker(url: string): Promise<Worker> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`DuckDB worker download failed (${res.status})`)
  const blobUrl = URL.createObjectURL(new Blob([await res.text()], { type: 'text/javascript' }))
  const worker = new Worker(blobUrl)
  URL.revokeObjectURL(blobUrl) // the worker has already started loading it
  return worker
}
