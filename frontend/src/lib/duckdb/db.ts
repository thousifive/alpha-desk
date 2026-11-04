import * as duckdb from '@duckdb/duckdb-wasm'
// Vite `?url` imports copy these into the build and give us their hashed URLs:
// self-hosted, so no CDN dependency at runtime.
import ehWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url'
import mvpWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url'
import ehWasm from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url'
import mvpWasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url'

import { API_BASE } from '../../api/client'
import type { ResultSet } from '../../api/types'
import { getToken } from '../auth/token'
import type { Bundle } from '../local/engine'
import { getCache } from '../local/store'
import { normalizeTable } from './normalize'

/** Must match backend/app/grading/dataset.py. */
export const TABLES = [
  'tickers',
  'prices',
  'factors',
  'trades',
  'positions',
  'corporate_actions',
] as const
export const MAX_RESULT_ROWS = 5_000

export interface QueryResult extends ResultSet {
  rowCount: number
  truncated: boolean
  elapsedMs: number
}

export type LoadProgress = { loaded: number; total: number }

let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null

/** One DuckDB instance per tab, created lazily on first use and shared after that. */
export function getDuckDB(onProgress?: (p: LoadProgress) => void): Promise<duckdb.AsyncDuckDB> {
  dbPromise ??= init(onProgress).catch((e: unknown) => {
    dbPromise = null // allow a retry after a failed load
    throw e
  })
  return dbPromise
}

async function init(onProgress?: (p: LoadProgress) => void): Promise<duckdb.AsyncDuckDB> {
  const bundle = await duckdb.selectBundle({
    mvp: { mainModule: mvpWasm, mainWorker: mvpWorker },
    eh: { mainModule: ehWasm, mainWorker: ehWorker },
  })
  const worker = new Worker(bundle.mainWorker!)
  const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)
  // Cast flags make BIGINT/HUGEINT/DECIMAL arrive as JS numbers instead of BigInt/Uint32Array,
  // matching the backend's normalization (see normalize.ts).
  await db.open({ query: { castBigIntToDouble: true, castDecimalToDouble: true } })

  const conn = await db.connect()
  let loaded = 0
  onProgress?.({ loaded, total: TABLES.length })
  // ?v= makes each dataset version its own URL, so the service worker can cache-first the
  // files (works offline) and still pick up a re-seeded dataset.
  const v = (await getCache<Bundle>('bundle'))?.dataset_version ?? '0'
  const token = getToken()
  await Promise.all(
    TABLES.map(async (t) => {
      const res = await fetch(`${API_BASE}/api/datasets/meridian/${t}.parquet?v=${v}`, {
        credentials: 'same-origin',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })
      if (!res.ok) throw new Error(`Failed to load ${t} (${res.status})`)
      await db.registerFileBuffer(`${t}.parquet`, new Uint8Array(await res.arrayBuffer()))
      onProgress?.({ loaded: ++loaded, total: TABLES.length })
    }),
  )
  // Tables, not views: same as the grader, so the planner sees identical inputs.
  for (const t of TABLES) {
    await conn.query(`CREATE TABLE ${t} AS SELECT * FROM read_parquet('${t}.parquet')`)
  }
  await conn.close()
  return db
}

export async function runQuery(sql: string): Promise<QueryResult> {
  const db = await getDuckDB()
  const conn = await db.connect()
  const t0 = performance.now()
  try {
    const table = await conn.query(sql)
    const normalized = normalizeTable(table, MAX_RESULT_ROWS)
    return { ...normalized, rowCount: table.numRows, elapsedMs: performance.now() - t0 }
  } finally {
    await conn.close()
  }
}

export async function describeSchema(): Promise<Record<string, { name: string; type: string }[]>> {
  const db = await getDuckDB()
  const conn = await db.connect()
  try {
    const t = await conn.query(
      `SELECT table_name, column_name, data_type FROM information_schema.columns
       WHERE table_schema = 'main' ORDER BY table_name, ordinal_position`,
    )
    const out: Record<string, { name: string; type: string }[]> = {}
    for (const row of t.toArray() as {
      table_name: string
      column_name: string
      data_type: string
    }[]) {
      ;(out[row.table_name] ??= []).push({ name: row.column_name, type: row.data_type })
    }
    return out
  } finally {
    await conn.close()
  }
}
