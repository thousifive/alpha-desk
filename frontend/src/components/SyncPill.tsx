import { Link } from 'react-router'

import { useQueuedCount, useSyncStatus } from '../lib/sync/hooks'
import { pillView } from '../lib/sync/pill'

/** Header status: calm grey when all is well, amber when progress is waiting on something. */
export function SyncPill() {
  const view = pillView(useSyncStatus(), useQueuedCount())
  const cls =
    view.tone === 'amber' ? 'border-amber/40 text-amber' : 'border-line text-muted hover:text-ink'
  return (
    // The link is a 44px touch target; the visible pill inside stays compact.
    <Link
      to="/settings"
      title={view.title}
      aria-live="polite"
      className="flex h-11 min-w-0 items-center"
    >
      <span
        className={`flex min-w-0 items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[11px] ${cls}`}
      >
        <span
          aria-hidden
          className={`size-1.5 shrink-0 rounded-full ${view.tone === 'amber' ? 'bg-amber' : 'bg-muted'}`}
        />
        <span className="truncate sm:hidden">{view.short}</span>
        <span className="hidden truncate sm:inline">{view.text}</span>
      </span>
    </Link>
  )
}
