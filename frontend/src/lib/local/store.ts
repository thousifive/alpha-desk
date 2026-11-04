import { getDB, type StoredEvent } from './db'
import type { LogEvent } from './events'

// The event log API. There is deliberately no delete and no update beyond the `synced` flag:
// events are facts, and an unsynced event may be the only copy of that progress anywhere.

type Listener = () => void
const listeners = new Set<Listener>()
// Other tabs of the app write to the same IndexedDB; tell them to recompute too.
const channel = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel('alpha-log')
channel?.addEventListener('message', () => notify(false))

function notify(broadcast = true) {
  for (const fn of listeners) fn()
  if (broadcast) channel?.postMessage('changed')
}

/** Something derived state depends on changed outside the log (e.g. a new content bundle). */
export const notifyChanged = () => notify()

export function onLogChange(fn: Listener): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

const now = () => new Date().toISOString()

export async function getDeviceId(): Promise<string> {
  const db = getDB()
  return db.transaction('rw', db.meta, async () => {
    const row = await db.meta.get('device_id')
    if (typeof row?.value === 'string') return row.value
    const id = crypto.randomUUID()
    await db.meta.put({ key: 'device_id', value: id, updated_at: now() })
    return id
  })
}

/**
 * Add events, skipping any id already stored (merge by id). Used for new local events,
 * imports, and (Part 2) events pulled from the server. Returns how many were new.
 */
export async function mergeEvents(events: LogEvent[], { synced = false } = {}): Promise<number> {
  if (events.length === 0) return 0
  const db = getDB()
  let upgraded = 0
  const added = await db.transaction('rw', db.events, async () => {
    const ids = [...new Set(events.map((e) => e.id))]
    const stored = await db.events.where('id').anyOf(ids).toArray()
    const existing = new Set(stored.map((e: StoredEvent) => e.id))
    if (synced) {
      // The server has these, so a local copy still marked unsynced (we crashed between the
      // upload succeeding and marking it) doesn't need uploading again.
      const stale = stored.filter((e) => e.synced === 0).map((e) => e.lseq!)
      upgraded = await db.events.where('lseq').anyOf(stale).modify({ synced: 1 })
    }
    const seen = new Set<string>()
    const fresh: StoredEvent[] = []
    for (const e of events) {
      if (existing.has(e.id) || seen.has(e.id)) continue
      seen.add(e.id)
      // Copy only envelope fields: a stray `lseq` from an import must not clash with ours.
      fresh.push({
        id: e.id,
        device_id: e.device_id,
        type: e.type,
        payload: e.payload,
        created_at: e.created_at,
        local_date: e.local_date,
        v: e.v ?? 1,
        synced: synced ? 1 : 0,
      })
    }
    await db.events.bulkAdd(fresh)
    return fresh.length
  })
  if (added || upgraded) notify()
  return added
}

/** The oldest `limit` events not yet on the server, in the order they were written. */
export async function unsyncedBatch(limit: number): Promise<StoredEvent[]> {
  // Compound filter instead of a [synced+lseq] index: the unsynced set is small (it only
  // holds what was written while offline), so scanning it is cheap.
  const rows = await getDB().events.where('synced').equals(0).sortBy('lseq')
  return rows.slice(0, limit)
}

/** The server confirmed these (accepted or already had them). The only field ever updated. */
export async function markSynced(ids: string[]): Promise<void> {
  if (ids.length === 0) return
  await getDB().events.where('id').anyOf(ids).modify({ synced: 1 })
  notify()
}

export async function eventsAfter(lseq: number): Promise<StoredEvent[]> {
  return getDB().events.where('lseq').above(lseq).sortBy('lseq')
}

export async function allEvents(): Promise<StoredEvent[]> {
  return getDB().events.orderBy('lseq').toArray()
}

export async function countEvents(): Promise<{ total: number; unsynced: number }> {
  const db = getDB()
  const [total, unsynced] = await Promise.all([
    db.events.count(),
    db.events.where('synced').equals(0).count(),
  ])
  return { total, unsynced }
}

export async function getCache<T>(key: string): Promise<T | undefined> {
  return (await getDB().cache.get(key))?.value as T | undefined
}

export async function setCache(key: string, value: unknown): Promise<void> {
  await getDB().cache.put({ key, value, updated_at: now() })
}

export async function getMeta<T>(key: string): Promise<T | undefined> {
  return (await getDB().meta.get(key))?.value as T | undefined
}

export async function setMeta(key: string, value: unknown): Promise<void> {
  await getDB().meta.put({ key, value, updated_at: now() })
}
