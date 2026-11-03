import type { Streak } from '../../api/types'
import { Panel } from '../../components/ui'

export function StreakCard({ streak }: { streak: Streak | null }) {
  if (!streak) {
    return (
      <Panel title="STREAK">
        <p className="font-mono text-3xl text-muted">—</p>
        <p className="mt-2 text-xs text-down">
          Streak offline: finish TODO(me) M2-1 <code className="font-mono">compute_streak</code>.
        </p>
      </Panel>
    )
  }
  const { current, best, freezes, max_freezes, active_today, next_milestone } = streak
  return (
    <Panel
      title="STREAK"
      right={
        <span
          className="flex gap-1"
          title={`${freezes}/${max_freezes} freeze tokens: each covers one missed day`}
        >
          {Array.from({ length: max_freezes }, (_, i) => (
            <span
              key={i}
              className={`font-mono text-xs ${i < freezes ? 'text-cyan' : 'text-line'}`}
              aria-hidden
            >
              ❄
            </span>
          ))}
          <span className="sr-only">
            {freezes} of {max_freezes} freeze tokens
          </span>
        </span>
      }
    >
      <p className="font-mono text-3xl font-semibold">
        <span className={active_today ? 'text-amber' : 'text-muted'}>▲ {current}</span>
        <span className="ml-2 text-base text-muted">day{current === 1 ? '' : 's'}</span>
      </p>
      <p className={`mt-2 font-mono text-xs ${active_today ? 'text-up' : 'text-muted'}`}>
        {active_today
          ? 'Today secured.'
          : current > 0
            ? 'Close one ticket today to keep it going.'
            : 'Close a ticket to start a streak.'}
      </p>
      <p className="mt-1 font-mono text-[11px] text-muted">
        best {best} · next milestone {next_milestone}
      </p>
    </Panel>
  )
}
