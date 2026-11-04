import type { ReactNode } from 'react'

import { useServerOnline } from '../lib/sync/hooks'

/**
 * Wrap anything that needs the backend live (AI hints, PM Chat, AI grading, Interview Arena).
 * Offline it shows a calm note instead of a button that would fail.
 */
export function ServerOnly({ children, label }: { children: ReactNode; label?: string }) {
  if (useServerOnline()) return <>{children}</>
  return (
    <span
      role="note"
      className="inline-flex min-h-11 items-center rounded border border-line px-3 font-mono text-xs text-muted"
    >
      {label ? `${label}: ` : ''}Available when the server is on
    </span>
  )
}
