import { API_BASE } from '../../api/client'

export type Reachability = 'unknown' | 'up' | 'down'

export interface HealthDeps {
  ping: () => Promise<boolean>
  isVisible: () => boolean
  setTimer: (fn: () => void, ms: number) => unknown
  clearTimer: (handle: unknown) => void
}

export const UP_INTERVAL_MS = 60_000
export const DOWN_BASE_MS = 10_000
export const DOWN_MAX_MS = 5 * 60_000
const NUDGE_THROTTLE_MS = 3_000

/**
 * Is the backend on? Checks /api/health on start, on focus/visibility/online (`nudge`), every
 * 60 s while up and visible, and with exponential backoff (10 s → 5 min) while down. Hidden
 * tabs don't poll at all. A failed check is an expected state, so nothing is logged.
 */
export class HealthMonitor {
  private state: Reachability = 'unknown'
  private failures = 0
  private timer: unknown = null
  private inFlight: Promise<Reachability> | null = null
  private lastCheck = 0
  private readonly listeners = new Set<(s: Reachability) => void>()
  private readonly deps: HealthDeps

  constructor(deps: HealthDeps) {
    this.deps = deps
  }

  get current(): Reachability {
    return this.state
  }

  subscribe(fn: (s: Reachability) => void): () => void {
    this.listeners.add(fn)
    return () => this.listeners.delete(fn)
  }

  /** Delay before the next scheduled check (exposed for tests). */
  nextDelay(): number {
    if (this.state !== 'down') return UP_INTERVAL_MS
    return Math.min(DOWN_BASE_MS * 2 ** (this.failures - 1), DOWN_MAX_MS)
  }

  check(): Promise<Reachability> {
    this.inFlight ??= this.run().finally(() => (this.inFlight = null))
    return this.inFlight
  }

  /** App opened, focused, or back online: check soon, but not on every focus flicker. */
  nudge(): void {
    if (Date.now() - this.lastCheck < NUDGE_THROTTLE_MS) return
    void this.check()
  }

  /** A real request failed or succeeded: no need to wait for the next poll to know. */
  report(ok: boolean): void {
    if (ok !== (this.state === 'up')) this.set(ok ? 'up' : 'down', ok)
  }

  stop(): void {
    if (this.timer !== null) this.deps.clearTimer(this.timer)
    this.timer = null
  }

  private async run(): Promise<Reachability> {
    this.lastCheck = Date.now()
    const ok = await this.deps.ping().catch(() => false)
    this.set(ok ? 'up' : 'down', ok)
    return this.state
  }

  private set(next: Reachability, ok: boolean) {
    this.failures = ok ? 0 : this.failures + 1
    const changed = next !== this.state
    this.state = next
    this.schedule()
    if (changed) for (const fn of this.listeners) fn(next)
  }

  private schedule() {
    this.stop()
    if (!this.deps.isVisible()) return // resumes on the next nudge (visibilitychange)
    this.timer = this.deps.setTimer(() => void this.check(), this.nextDelay())
  }
}

async function pingHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(4_000),
    })
    return res.ok
  } catch {
    return false
  }
}

let monitor: HealthMonitor | null = null

export function getHealth(): HealthMonitor {
  monitor ??= new HealthMonitor({
    ping: pingHealth,
    isVisible: () => document.visibilityState === 'visible',
    setTimer: (fn, ms) => window.setTimeout(fn, ms),
    clearTimer: (h) => window.clearTimeout(h as number),
  })
  return monitor
}

/** Wire the browser signals that should trigger an immediate check. Returns an unsubscribe. */
export function watchBrowserSignals(m: HealthMonitor): () => void {
  const nudge = () => m.nudge()
  const onVisibility = () => (document.visibilityState === 'visible' ? m.nudge() : m.stop())
  window.addEventListener('focus', nudge)
  window.addEventListener('online', nudge)
  document.addEventListener('visibilitychange', onVisibility)
  m.nudge()
  return () => {
    window.removeEventListener('focus', nudge)
    window.removeEventListener('online', nudge)
    document.removeEventListener('visibilitychange', onVisibility)
    m.stop()
  }
}
