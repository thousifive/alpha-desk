import { useState } from 'react'

import type { Schema } from '../../lib/duckdb/useDuckDB'

export function SchemaPanel({ schema }: { schema: Schema }) {
  const [open, setOpen] = useState<string | null>(null)
  return (
    <section className="mt-6">
      <h2 className="font-mono text-[11px] tracking-wider text-muted">TABLES</h2>
      <ul className="mt-2 space-y-0.5 font-mono text-xs">
        {Object.entries(schema).map(([table, cols]) => (
          <li key={table}>
            <button
              onClick={() => setOpen(open === table ? null : table)}
              className="flex w-full items-center gap-2 rounded px-1.5 py-1 text-left hover:bg-panel-2"
              aria-expanded={open === table}
            >
              <span className="text-muted">{open === table ? '▾' : '▸'}</span>
              <span className="text-cyan">{table}</span>
              <span className="ml-auto text-muted">{cols.length}</span>
            </button>
            {open === table && (
              <ul className="mb-1 ml-6 border-l border-line pl-2">
                {cols.map((c) => (
                  <li key={c.name} className="flex justify-between gap-2 py-0.5">
                    <span>{c.name}</span>
                    <span className="text-muted">{c.type.toLowerCase()}</span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
