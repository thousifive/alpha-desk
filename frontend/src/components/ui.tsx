import type { ReactNode } from 'react'

import type { NodeState } from '../api/types'

export function Panel({
  title,
  right,
  children,
  className = '',
}: {
  title: string
  right?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-lg border border-line bg-panel ${className}`}>
      <header className="flex items-center justify-between border-b border-line px-4 py-2">
        <h2 className="font-mono text-[11px] tracking-wider text-muted">{title}</h2>
        {right}
      </header>
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Bar({ value, className = 'bg-amber' }: { value: number; className?: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-line"
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full rounded-full transition-[width] duration-700 ${className}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

const STATE_STYLE: Record<NodeState, { label: string; cls: string }> = {
  mastered: { label: 'MASTERED', cls: 'text-up border-up/40 bg-up/10' },
  available: { label: 'OPEN', cls: 'text-amber border-amber/40 bg-amber/10' },
  locked: { label: 'LOCKED', cls: 'text-muted border-line bg-panel-2' },
  coming_soon: { label: 'SOON', cls: 'text-muted/70 border-line bg-panel-2' },
}

export function StateBadge({ state }: { state: NodeState }) {
  const s = STATE_STYLE[state]
  return (
    <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${s.cls}`}>{s.label}</span>
  )
}
