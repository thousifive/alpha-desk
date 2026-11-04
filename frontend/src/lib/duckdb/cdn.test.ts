import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { expect, it } from 'vitest'

import { DUCKDB_BUNDLES, DUCKDB_VERSION } from './cdn'

it('DUCKDB_VERSION matches the pinned npm package (JS API and WASM must agree)', () => {
  const pkg = JSON.parse(readFileSync(resolve(__dirname, '../../../package.json'), 'utf8')) as {
    dependencies: Record<string, string>
  }
  expect(pkg.dependencies['@duckdb/duckdb-wasm']).toBe(DUCKDB_VERSION)
})

it('every bundle file exists in the installed package (catches renames on upgrade)', () => {
  const dist = resolve(__dirname, '../../../node_modules/@duckdb/duckdb-wasm/dist')
  for (const b of Object.values(DUCKDB_BUNDLES)) {
    for (const url of [b.mainModule, b.mainWorker]) {
      expect(() => readFileSync(resolve(dist, url.split('/').pop()!))).not.toThrow()
    }
  }
})
