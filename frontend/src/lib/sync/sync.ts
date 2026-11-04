import { ApiError, api } from '../../api/client'
import { setToken, tokenExpiresAt, type StoredToken } from '../auth/token'
import { questPlanKey, type Bundle, type QuestPlan } from '../local/engine'
import { localDate, type LogEvent } from '../local/events'
import {
  getCache,
  getMeta,
  markSynced,
  mergeEvents,
  notifyChanged,
  setCache,
  setMeta,
  unsyncedBatch,
} from '../local/store'

// One sync pass against a reachable server. Every step is safe to interrupt and re-run:
// uploads are idempotent by event id, and the download cursor only moves after a page has
// been stored. So "phone locked mid-sync" just means the next pass redoes a little work.

export interface IngestResult {
  accepted: number
  duplicates: number
  rejected: number
}

export interface EventPage {
  events: LogEvent[]
  cursor: number
  more: boolean
}

export interface SyncApi {
  bundle(): Promise<Bundle>
  legacyEvents(): Promise<LogEvent[]>
  postEvents(batch: LogEvent[]): Promise<IngestResult>
  getEvents(since: number, limit: number): Promise<EventPage>
  questPlans(from: string, days: number): Promise<{ plans: QuestPlan[] }>
  refreshToken(): Promise<StoredToken>
  setTimezone(tz: string): Promise<unknown>
}

export const httpSyncApi: SyncApi = {
  bundle: () => api.get('/offline/bundle'),
  legacyEvents: () => api.get('/offline/legacy-events'),
  postEvents: (batch) => api.post('/sync/events', batch),
  getEvents: (since, limit) => api.get(`/sync/events?since=${since}&limit=${limit}`),
  questPlans: (from, days) => api.get(`/sync/quests?from=${from}&days=${days}`),
  refreshToken: () => api.post('/auth/refresh'),
  setTimezone: (timezone) => api.put('/auth/timezone', { timezone }),
}

export const PUSH_BATCH = 200
export const PULL_PAGE = 500
export const PLAN_DAYS = 3
// Swap the token for a fresh one at most once a day (it's valid for 30).
const TOKEN_REFRESH_AFTER_MS = 86_400_000
const TOKEN_LIFETIME_MS = 30 * 86_400_000

export interface SyncReport {
  pushed: number
  pulled: number
  rejected: number
  plans: number
  /** 501 messages from steps still waiting on a TODO(me). The other steps still ran. */
  locked: string[]
  /** Both directions of the event log went through. */
  complete: boolean
}

const strip = ({ lseq: _l, synced: _s, ...e }: LogEvent & { lseq?: number; synced?: 0 | 1 }) => e

/** Upload unsynced events oldest first, in batches; each batch is marked synced on success. */
export async function push(api: SyncApi): Promise<{ accepted: number; rejected: number }> {
  let accepted = 0
  let rejected = 0
  for (;;) {
    const batch = await unsyncedBatch(PUSH_BATCH)
    if (batch.length === 0) break
    const res = await api.postEvents(batch.map(strip))
    // Rejected events are marked too: the server will never take them, and re-sending them
    // forever would make every sync fail the same way. They stay in the local log and backups.
    await markSynced(batch.map((e) => e.id))
    accepted += res.accepted
    rejected += res.rejected
    if (batch.length < PUSH_BATCH) break
  }
  if (rejected)
    await setMeta('sync_rejected', ((await getMeta<number>('sync_rejected')) ?? 0) + rejected)
  return { accepted, rejected }
}

/** Download everything after our cursor (including our own uploads: merge skips those). */
export async function pull(api: SyncApi): Promise<number> {
  let cursor = (await getMeta<number>('sync_cursor')) ?? 0
  let added = 0
  for (;;) {
    const page = await api.getEvents(cursor, PULL_PAGE)
    added += await mergeEvents(page.events, { synced: true })
    // Advance only after the page is stored: a crash here means re-fetching one page.
    cursor = page.cursor
    await setMeta('sync_cursor', cursor)
    if (!page.more) break
  }
  return added
}

/** Fetch and cache quest plans for today and the next days, so they work with the server off. */
export async function prefetchQuests(api: SyncApi, today: string): Promise<number> {
  const { plans } = await api.questPlans(today, PLAN_DAYS)
  for (const p of plans) await setCache(questPlanKey(p.day), p)
  return plans.length
}

async function refreshBundle(api: SyncApi): Promise<void> {
  const bundle = await api.bundle()
  const current = await getCache<Bundle>('bundle')
  if (current?.version !== bundle.version) {
    await setCache('bundle', bundle)
    notifyChanged() // the rules worker reloads on the next query
  }
}

async function importLegacyOnce(api: SyncApi): Promise<void> {
  if (await getMeta<boolean>('legacy_imported')) return
  // Marked synced: they came *from* the server, there's nothing to upload.
  await mergeEvents(await api.legacyEvents(), { synced: true })
  await setMeta('legacy_imported', true)
}

async function maybeRefreshToken(api: SyncApi): Promise<void> {
  const exp = tokenExpiresAt()
  if (exp === null || exp - Date.now() > TOKEN_LIFETIME_MS - TOKEN_REFRESH_AFTER_MS) return
  await setToken(await api.refreshToken())
}

const isLocked = (e: unknown): e is ApiError => e instanceof ApiError && e.status === 501

export async function runSync(
  api: SyncApi = httpSyncApi,
  { today = localDate(), timezone }: { today?: string; timezone?: string } = {},
): Promise<SyncReport> {
  const report: SyncReport = {
    pushed: 0,
    pulled: 0,
    rejected: 0,
    plans: 0,
    locked: [],
    complete: false,
  }
  let logOk = true
  // A step waiting on a TODO(me) is noted and skipped; anything else (offline, 5xx) aborts
  // the pass, and the caller retries on the next health check.
  const step = async (fn: () => Promise<void>, partOfLog = false) => {
    try {
      await fn()
    } catch (e) {
      if (!isLocked(e)) throw e
      report.locked.push(e.message)
      if (partOfLog) logOk = false
    }
  }

  await step(() => refreshBundle(api))
  await step(() => importLegacyOnce(api))
  if (timezone) await step(async () => void (await api.setTimezone(timezone)))
  await step(async () => {
    const r = await push(api)
    report.pushed = r.accepted
    report.rejected = r.rejected
  }, true)
  await step(async () => void (report.pulled = await pull(api)), true)
  // After the upload, so the server picks quests knowing what was just passed offline.
  await step(async () => void (report.plans = await prefetchQuests(api, today)))
  await step(() => maybeRefreshToken(api))

  report.complete = logOk
  if (logOk) await setMeta('last_sync_at', new Date().toISOString())
  return report
}
