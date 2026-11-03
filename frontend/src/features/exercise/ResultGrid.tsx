import type { Cell } from '../../api/types'
import type { QueryResult } from '../../lib/duckdb/db'

const RENDER_CAP = 200 // DOM rows; grading still uses the full (capped at 5k) result

export function ResultGrid({ result }: { result: QueryResult }) {
  const shown = result.rows.slice(0, RENDER_CAP)
  const numericCol = result.columns.map(
    (_, c) =>
      shown.some((r) => typeof r[c] === 'number') &&
      shown.every((r) => r[c] === null || typeof r[c] === 'number'),
  )
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-line px-3 py-1.5 font-mono text-[11px] text-muted">
        <span>
          {result.rowCount.toLocaleString()} row{result.rowCount === 1 ? '' : 's'}
        </span>
        <span>{result.elapsedMs.toFixed(1)} ms</span>
        {result.rows.length > RENDER_CAP && <span>showing first {RENDER_CAP}</span>}
        {result.truncated && (
          <span className="text-down">result capped at 5,000 rows for grading</span>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse font-mono text-xs">
          <thead className="sticky top-0 bg-panel-2">
            <tr>
              {result.columns.map((c, i) => (
                <th
                  key={i}
                  className={`border-b border-line px-3 py-1.5 font-medium text-muted ${numericCol[i] ? 'text-right' : 'text-left'}`}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, r) => (
              <tr key={r} className="odd:bg-panel/40 hover:bg-panel-2">
                {row.map((v, c) => (
                  <td
                    key={c}
                    className={`whitespace-nowrap px-3 py-1 ${numericCol[c] ? 'text-right' : ''}`}
                  >
                    <CellView v={v} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function CellView({ v }: { v: Cell }) {
  if (v === null) return <span className="text-muted/60">NULL</span>
  if (typeof v === 'number') {
    const s = Number.isInteger(v)
      ? v.toLocaleString()
      : v.toLocaleString(undefined, { maximumFractionDigits: 6 })
    return <span className={v < 0 ? 'text-down' : ''}>{s}</span>
  }
  if (typeof v === 'boolean') return <span className="text-cyan">{String(v)}</span>
  return <>{v}</>
}
