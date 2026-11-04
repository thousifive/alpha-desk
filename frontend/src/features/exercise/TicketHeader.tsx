import { Link } from 'react-router'

import type { Exercise } from '../../api/types'
import { PERSONAS } from '../../lib/personas'

export function TicketHeader({ ex }: { ex: Exercise }) {
  const p = PERSONAS[ex.persona]
  return (
    <header>
      <p className="font-mono text-[11px] text-muted">
        <Link
          to={`/branches/${ex.branch_id}`}
          className="hover:text-ink pointer-coarse:inline-flex pointer-coarse:min-h-11 pointer-coarse:items-center"
        >
          {ex.branch_id.toUpperCase()}
        </Link>
        <span className="mx-1.5">/</span>
        {ex.node_title.toUpperCase()}
      </p>
      <div className="mt-3 flex items-center gap-3">
        <span
          className="grid size-9 shrink-0 place-items-center rounded-full font-mono text-sm font-semibold text-bg"
          style={{ background: p.color }}
          aria-hidden
        >
          {p.name[0]}
        </span>
        <div className="min-w-0">
          <p className="text-sm">
            <span style={{ color: p.color }}>{p.name}</span>
            <span className="text-muted"> · {p.role}</span>
          </p>
          <h1 className="truncate text-lg font-semibold">{ex.title}</h1>
        </div>
        <Difficulty level={ex.difficulty} />
      </div>
    </header>
  )
}

export function Difficulty({ level }: { level: number }) {
  return (
    <span
      className="ml-auto flex gap-0.5"
      title={`Difficulty ${level}/3`}
      aria-label={`Difficulty ${level} of 3`}
    >
      {[1, 2, 3].map((i) => (
        <span key={i} className={`h-3 w-1.5 rounded-sm ${i <= level ? 'bg-amber' : 'bg-line'}`} />
      ))}
    </span>
  )
}
