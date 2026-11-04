import { useRegisterSW } from 'virtual:pwa-register/react'

const UPDATE_CHECK_MS = 60 * 60_000

/**
 * New deploy available: ask, don't auto-reload (an exercise draft could be mid-edit). The
 * service worker installs the new version in the background; tapping activates it and reloads.
 */
export function UpdateToast() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    // A PWA left open for days never navigates, so the browser never re-checks on its own.
    onRegisteredSW(_url, reg) {
      if (reg) setInterval(() => void reg.update().catch(() => undefined), UPDATE_CHECK_MS)
    },
  })
  if (!needRefresh) return null
  return (
    <div
      role="status"
      className="fixed inset-x-0 bottom-0 z-50 flex justify-center px-4"
      style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}
    >
      <div className="flex items-center gap-2 rounded-lg border border-amber/40 bg-panel shadow-lg">
        <button
          onClick={() => void updateServiceWorker(true)}
          className="min-h-11 px-4 font-mono text-xs text-amber"
        >
          Update available · tap to reload
        </button>
        <button
          onClick={() => setNeedRefresh(false)}
          aria-label="Dismiss"
          className="min-h-11 min-w-11 border-l border-line font-mono text-xs text-muted"
        >
          ✕
        </button>
      </div>
    </div>
  )
}
