import { ApiError } from '../api/client'
import { NoBundleError } from '../lib/local/engine'

/** Page-level load failure. A missing bundle on a fresh device is expected, not an error. */
export function LoadError({ error, notFound }: { error: unknown; notFound: string }) {
  if (error instanceof NoBundleError) {
    return (
      <div className="p-6 font-mono text-sm">
        <p className="text-amber">Desk not downloaded yet.</p>
        <p className="mt-1 text-xs text-muted">
          Open Alpha Desk once while the server is on. After that it works offline.
        </p>
      </div>
    )
  }
  const msg = error instanceof ApiError && error.status === 404 ? notFound : 'Failed to load.'
  return <p className="p-6 font-mono text-sm text-down">{msg}</p>
}
