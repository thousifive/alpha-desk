import { useEffect, useRef } from 'react'

export interface Hotkeys {
  onRun?: () => void
  onSubmit?: () => void
}

/** Matches Cmd+Enter / Cmd+Shift+Enter (Ctrl on non-Mac). Exported for tests. */
export function matchHotkey(e: Pick<KeyboardEvent, 'key' | 'metaKey' | 'ctrlKey' | 'shiftKey'>) {
  if (e.key !== 'Enter' || !(e.metaKey || e.ctrlKey)) return null
  return e.shiftKey ? 'submit' : 'run'
}

/**
 * Global Cmd+Enter (run) / Cmd+Shift+Enter (submit). Monaco registers the same bindings
 * as editor commands (it swallows keydown), so this covers focus anywhere else on the page.
 * Handlers live in a ref so callers can pass inline closures without re-binding listeners.
 */
export function useHotkeys(handlers: Hotkeys) {
  const ref = useRef(handlers)
  useEffect(() => {
    ref.current = handlers
  })
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const action = matchHotkey(e)
      if (!action) return
      e.preventDefault()
      if (action === 'submit') ref.current.onSubmit?.()
      else ref.current.onRun?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}
