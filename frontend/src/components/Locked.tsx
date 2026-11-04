import { PERSONAS } from '../lib/personas'
import type { TodoTask } from '../lib/todos'

export function Padlock({ className = 'size-3.5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} aria-hidden>
      <rect x="3" y="7" width="10" height="7" rx="1.5" fill="currentColor" opacity="0.25" />
      <rect x="3" y="7" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  )
}

/**
 * An expected, not-yet-built feature waiting on a TODO(me). Calm amber/grey styling, never the
 * red error color: nothing is broken, the PR just hasn't landed.
 */
export function Locked({ task, compact = false }: { task: TodoTask; compact?: boolean }) {
  const p = PERSONAS[task.persona]
  if (compact) {
    return (
      <span
        role="status"
        className="inline-flex items-center gap-1.5 font-mono text-xs text-amber/90"
        title={`TODO(me) ${task.id}: ${task.fn}() in ${task.file}`}
      >
        <Padlock />
        Locked: TODO(me) {task.id} <code>{task.fn}()</code>
      </span>
    )
  }
  return (
    <div role="status" className="rounded-md border border-amber/25 bg-amber/5 p-3 text-xs">
      <p className="flex items-center gap-1.5 font-mono text-[10px] tracking-wider text-amber">
        <Padlock /> LOCKED
      </p>
      <p className="mt-1.5 text-ink/90">
        <span className="font-semibold" style={{ color: p.color }}>
          {p.name}:
        </span>{' '}
        {task.story}
      </p>
      <p className="mt-1.5 font-mono text-[11px] text-muted">
        TODO(me) {task.id} · <code className="text-ink/80">{task.fn}()</code> · {task.file}
      </p>
    </div>
  )
}
