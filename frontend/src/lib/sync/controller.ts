import type { QueryClient } from '@tanstack/react-query'

import { OfflineError } from '../../api/client'
import { onTokenChange, isAuthenticated } from '../auth/token'
import { countEvents, getMeta, onLogChange } from '../local/store'
import { getHealth, watchBrowserSignals, type HealthMonitor } from './health'
import { httpSyncApi, runSync, type SyncApi } from './sync'

// Decides *when* to sync: when the server comes back, shortly after new local progress, and
// every few minutes while it stays up (to pick up other devices' progress). Exposes a small
// observable status for the header pill.

export interface SyncStatus {
  reachability: 'unknown' | 'up' | 'down'
  syncing: boolean
  lastSyncAt: string | null
  /** 501 messages from the last pass: which TODO(me) is holding a step back. */
  locked: string[]
}

let status: SyncStatus = { reachability: 'unknown', syncing: false, lastSyncAt: null, locked: [] }
const listeners = new Set<() => void>()

function update(patch: Partial<SyncStatus>) {
  status = { ...status, ...patch }
  for (const fn of listeners) fn()
}

export const getSyncStatus = () => status
export function subscribeSyncStatus(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export const PERIODIC_SYNC_MS = 3 * 60_000
const LOCAL_CHANGE_DEBOUNCE_MS = 2_000

export class SyncController {
  private running: Promise<void> | null = null
  private again = false
  private readonly health: HealthMonitor
  private readonly api: SyncApi
  private readonly onSynced: () => void

  constructor(health: HealthMonitor, api: SyncApi, onSynced: () => void) {
    this.health = health
    this.api = api
    this.onSynced = onSynced
  }

  /** Run a pass now (or right after the current one). Resolves when it's done. */
  request(): Promise<void> {
    if (this.running) {
      this.again = true
      return this.running
    }
    this.running = this.loop().finally(() => (this.running = null))
    return this.running
  }

  private async loop(): Promise<void> {
    do {
      this.again = false
      await this.once()
    } while (this.again)
  }

  private async once(): Promise<void> {
    if (this.health.current !== 'up' || !isAuthenticated()) return
    update({ syncing: true })
    try {
      const report = await withSyncLock(() =>
        runSync(this.api, { timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }),
      )
      if (report) update({ locked: report.locked })
      this.health.report(true)
      this.onSynced()
    } catch (e) {
      // Offline mid-sync is routine; the next health check retries. Other failures (a 5xx)
      // also just wait for the next pass: nothing is lost, the log is still local.
      if (e instanceof OfflineError) this.health.report(false)
    } finally {
      update({ syncing: false, lastSyncAt: (await getMeta<string>('last_sync_at')) ?? null })
    }
  }
}

/** Two open tabs shouldn't sync at the same time. Web Locks where available; else just run. */
async function withSyncLock<T>(fn: () => Promise<T>): Promise<T | null> {
  if (typeof navigator === 'undefined' || !('locks' in navigator)) return fn()
  return navigator.locks.request('alpha-desk-sync', { ifAvailable: true }, (lock) =>
    lock ? fn() : null,
  )
}

let controller: SyncController | null = null

/** Sync now, e.g. from the Settings button. No-op while the server is down. */
export const syncNow = () => controller?.request() ?? Promise.resolve()

/** Start health checks and the sync triggers. Call once from the app shell. */
export function startSync(qc: QueryClient): () => void {
  const health = getHealth()
  // Recompute every local view after a pass: new events, a new bundle, or new quest plans.
  const c = new SyncController(health, httpSyncApi, () => {
    void qc.invalidateQueries({ queryKey: ['local'] })
  })
  controller = c
  void getMeta<string>('last_sync_at').then((t) => update({ lastSyncAt: t ?? null }))

  const offHealth = health.subscribe((r) => {
    update({ reachability: r })
    if (r === 'up') void c.request()
  })
  update({ reachability: health.current })

  let debounce: ReturnType<typeof setTimeout> | undefined
  const offLog = onLogChange(() => {
    clearTimeout(debounce)
    debounce = setTimeout(() => {
      // Only our own new events need a push; a pull's merge also fires this, so check.
      void countEvents().then(({ unsynced }) => unsynced > 0 && void c.request())
    }, LOCAL_CHANGE_DEBOUNCE_MS)
  })
  const offToken = onTokenChange(() => void c.request()) // just logged in
  const periodic = setInterval(() => {
    if (document.visibilityState === 'visible') void c.request()
  }, PERIODIC_SYNC_MS)
  const offSignals = watchBrowserSignals(health)

  return () => {
    offHealth()
    offLog()
    offToken()
    offSignals()
    clearInterval(periodic)
    clearTimeout(debounce)
    if (controller === c) controller = null
  }
}
