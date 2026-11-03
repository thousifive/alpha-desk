import { Type, type Table } from 'apache-arrow'

import type { Cell, ResultSet } from '../../api/types'

/**
 * Arrow result → JSON-safe rows, matching backend/app/grading/sql.py's normalization contract:
 *   DATE      → "YYYY-MM-DD"
 *   TIMESTAMP → "YYYY-MM-DDTHH:MM:SS" (+ ".ffffff" only when microseconds ≠ 0)
 *   numbers   → number (BIGINT/HUGEINT/DECIMAL arrive as doubles via the db.open() cast flags)
 *
 * DuckDB-WASM hands DATE and TIMESTAMP back as epoch milliseconds (UTC). Timestamps keep
 * microseconds as the fractional part of the millisecond value.
 */
export function normalizeTable(table: Table, maxRows: number): ResultSet & { truncated: boolean } {
  const fields = table.schema.fields
  const columns = fields.map((f) => f.name)
  const convert = fields.map((f) => converterFor(f.type.typeId))
  const vectors = fields.map((f) => table.getChild(f.name))
  const n = Math.min(table.numRows, maxRows)

  const rows: Cell[][] = new Array(n)
  for (let i = 0; i < n; i++) {
    const row: Cell[] = new Array(fields.length)
    for (let c = 0; c < fields.length; c++) {
      const v: unknown = vectors[c]?.get(i)
      row[c] = v === null || v === undefined ? null : convert[c]!(v)
    }
    rows[i] = row
  }
  return { columns, rows, truncated: table.numRows > maxRows }
}

type Converter = (v: unknown) => Cell

function converterFor(typeId: Type): Converter {
  switch (typeId) {
    case Type.Date:
    case Type.DateDay:
    case Type.DateMillisecond:
      return (v) => formatDate(toMs(v))
    case Type.Timestamp:
    case Type.TimestampSecond:
    case Type.TimestampMillisecond:
    case Type.TimestampMicrosecond:
    case Type.TimestampNanosecond:
      return (v) => formatTimestamp(toMs(v))
    default:
      return scalar
  }
}

function toMs(v: unknown): number {
  if (v instanceof Date) return v.getTime()
  if (typeof v === 'bigint') return Number(v)
  return v as number
}

function scalar(v: unknown): Cell {
  if (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') return v
  if (typeof v === 'bigint') return Number(v) // fallback if a cast flag is ever off
  return String(v)
}

const pad = (n: number, w = 2) => String(n).padStart(w, '0')

export function formatDate(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

export function formatTimestamp(ms: number): string {
  const wholeMs = Math.floor(ms)
  const d = new Date(wholeMs)
  const base =
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
  const micros = d.getUTCMilliseconds() * 1000 + Math.round((ms - wholeMs) * 1000)
  return micros === 0 ? base : `${base}.${pad(micros, 6)}`
}
