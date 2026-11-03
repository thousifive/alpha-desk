import { tableFromArrays } from 'apache-arrow'
import { describe, expect, it } from 'vitest'

import { formatDate, formatTimestamp, normalizeTable } from './normalize'

describe('date/timestamp formatting (must match backend normalize_value)', () => {
  it('formats DATE epoch-ms as YYYY-MM-DD in UTC', () => {
    expect(formatDate(Date.UTC(2025, 0, 2))).toBe('2025-01-02')
  })

  it('formats midnight timestamps without fractional seconds', () => {
    expect(formatTimestamp(Date.UTC(2025, 9, 6))).toBe('2025-10-06T00:00:00')
  })

  it('keeps microseconds carried as fractional milliseconds', () => {
    // DuckDB-WASM returns 09:30:00.000123 as ...000.123 ms
    expect(formatTimestamp(Date.UTC(2025, 0, 2, 9, 30) + 0.123)).toBe('2025-01-02T09:30:00.000123')
    expect(formatTimestamp(Date.UTC(2025, 0, 2, 9, 30, 1, 250))).toBe('2025-01-02T09:30:01.250000')
  })
})

describe('normalizeTable', () => {
  const table = tableFromArrays({
    ticker: ['AAA', 'BBB', 'CCC'],
    ret: Float64Array.from([0.1, -0.2, 0.3]),
    n: Int32Array.from([1, 2, 3]),
  })

  it('returns columns and plain-JS rows', () => {
    const out = normalizeTable(table, 10)
    expect(out.columns).toEqual(['ticker', 'ret', 'n'])
    expect(out.rows).toEqual([
      ['AAA', 0.1, 1],
      ['BBB', -0.2, 2],
      ['CCC', 0.3, 3],
    ])
    expect(out.truncated).toBe(false)
  })

  it('caps rows and flags truncation', () => {
    const out = normalizeTable(table, 2)
    expect(out.rows).toHaveLength(2)
    expect(out.truncated).toBe(true)
  })

  it('maps nulls to null', () => {
    const t = tableFromArrays({ x: ['a', null as unknown as string] })
    expect(normalizeTable(t, 10).rows).toEqual([['a'], [null]])
  })
})
