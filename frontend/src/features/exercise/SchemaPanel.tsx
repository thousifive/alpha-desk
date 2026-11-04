import { useState } from 'react'

import type { Schema } from '../../lib/duckdb/useDuckDB'

export function SchemaPanel({ schema }: { schema: Schema }) {
  const [open, setOpen] = useState<string | null>(null)
  // On a phone the list sits between the prompt and the editor: start collapsed so the editor
  // is one short scroll away. Decided once at mount.
  const [shown, setShown] = useState(() => !window.matchMedia('(max-width: 639px)').matches)
  const count = Object.keys(schema).length
  return (
    <section className="mt-6">
      <button
        onClick={() => setShown(!shown)}
        aria-expanded={shown}
        className="flex items-center gap-2 font-mono text-[11px] tracking-wider text-muted hover:text-ink pointer-coarse:min-h-11"
      >
        <span>{shown ? '▾' : '▸'}</span>
        TABLES ({count})
      </button>
      <ul hidden={!shown} className="mt-2 space-y-0.5 font-mono text-xs">
        {Object.entries(schema).map(([table, cols]) => (
          <li key={table}>
            <button
              onClick={() => setOpen(open === table ? null : table)}
              className="flex w-full items-center gap-2 rounded px-1.5 py-1 text-left hover:bg-panel-2 pointer-coarse:min-h-11"
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
