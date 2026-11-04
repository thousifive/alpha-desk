import { getDB, type StoredEvent } from './db'
import type { LogEvent } from './events'

// The event log API. There is deliberately no update or delete: events are facts, and an
// unsynced event may be the only copy of that progress anywhere.

type Listener = () => void
const listeners = new Set<Listener>()
// Other tabs of the app write to the same IndexedDB; tell them to recompute too.
const channel = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel('alpha-log')
channel?.addEventListener('message', () => notify(false))

function notify(broadcast = true) {
  for (const fn of listeners) fn()
  if (broadcast) channel?.postMessage('changed')
}

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
  const added = await db.transaction('rw', db.events, async () => {
    const ids = [...new Set(events.map((e) => e.id))]
    const existing = new Set(
      (await db.events.where('id').anyOf(ids).toArray()).map((e: StoredEvent) => e.id),
    )
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
  if (added) notify()
  return added
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
