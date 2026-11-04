import { beforeEach, describe, expect, it } from 'vitest'

import { ApiError, OfflineError } from '../../api/client'
import { questPlanKey, type Bundle, type QuestPlan } from '../local/engine'
import type { LogEvent } from '../local/events'
import { allEvents, countEvents, getCache, getMeta, mergeEvents, setCache } from '../local/store'
import { ev, freshDB } from '../local/testing'
import { PUSH_BATCH, pull, push, runSync, type SyncApi } from './sync'

/** An in-memory server with the same contract as /api/sync: dedupe by id, seq cursor. */
class FakeServer implements SyncApi {
  log: LogEvent[] = []
  posts = 0
  failAfterStore: number | null = null // drop the response of this POST (1-based)
  failPullAt: number | null = null
  pulls = 0
  locked = new Set<string>()
  plans: QuestPlan[] = []

  async bundle(): Promise<Bundle> {
    return { version: 'v1', milestone: 'M2', content: {} }
  }
  async legacyEvents() {
    return []
  }
  async postEvents(batch: LogEvent[]) {
    if (this.locked.has('post')) throw new ApiError(501, 'Sync offline: TODO(me) M2.5-1: x')
    this.posts++
    const ids = new Set(this.log.map((e) => e.id))
    let accepted = 0
    for (const e of batch) {
      if (ids.has(e.id)) continue
      ids.add(e.id)
      this.log.push(e)
      accepted++
    }
    // Stored, but the phone never hears back (went to sleep, tunnel blipped).
    if (this.posts === this.failAfterStore) throw new OfflineError()
    return { accepted, duplicates: batch.length - accepted, rejected: 0 }
  }
  async getEvents(since: number, limit: number) {
    if (this.locked.has('get')) throw new ApiError(501, 'Sync offline: TODO(me) M2.5-2: x')
    if (++this.pulls === this.failPullAt) throw new OfflineError()
    const events = this.log.slice(since, since + limit) // seq = index + 1
    return { events, cursor: since + events.length, more: since + limit < this.log.length }
  }
  async questPlans(from: string, days: number) {
    if (this.locked.has('quests')) throw new ApiError(501, 'Quest board offline: TODO(me) M2-2')
    const day0 = new Date(`${from}T12:00:00Z`)
    this.plans = Array.from({ length: days }, (_, i) => {
      const d = new Date(day0)
      d.setUTCDate(d.getUTCDate() + i)
      return { day: d.toISOString().slice(0, 10), items: [[0, `ex-${i}`]] as [number, string][] }
    })
    return { plans: this.plans }
  }
  async refreshToken() {
    return { token: 't', expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString() }
  }
  async setTimezone() {
    return {}
  }
}

const device = (name: string, n: number, from = 0) =>
  Array.from({ length: n }, (_, i) =>
    ev(from + i, {
      id: `${name.padEnd(8, '0').slice(0, 8)}-0000-4000-8000-${String(from + i).padStart(12, '0')}`,
      device_id: name,
    }),
  )

describe('sync', () => {
  let server: FakeServer
  beforeEach(() => {
    freshDB()
    server = new FakeServer()
  })

  it('merges two devices through the server', async () => {
    const phone = freshDB()
    await mergeEvents(device('phone', 3))
    await runSync(server)
    freshDB() // the iPad
    await mergeEvents(device('ipad', 2))
    await runSync(server)
    expect((await allEvents()).length).toBe(5) // iPad got the phone's three
    const { setDBForTests } = await import('../local/db')
    setDBForTests(phone)
    await runSync(server)
    expect((await allEvents()).map((e) => e.device_id).sort()).toEqual([
      'ipad',
      'ipad',
      'phone',
      'phone',
      'phone',
    ])
    expect(await countEvents()).toEqual({ total: 5, unsynced: 0 })
    expect(server.log.length).toBe(5) // own events pulled back were not re-uploaded
  })

  it('resumes after a batch whose response was lost', async () => {
    await mergeEvents(device('phone', PUSH_BATCH + 50))
    server.failAfterStore = 2 // second batch stored server-side, phone never knew
    await expect(push(server)).rejects.toBeInstanceOf(OfflineError)
    expect((await countEvents()).unsynced).toBe(50)
    const r = await push(server)
    expect(r.accepted).toBe(0) // the re-sent batch was all duplicates
    expect(server.log.length).toBe(PUSH_BATCH + 50)
    expect((await countEvents()).unsynced).toBe(0)
  })

  it('a pull interrupted between pages continues from the stored cursor', async () => {
    server.log = device('ipad', 1200)
    server.failPullAt = 2
    await expect(pull(server)).rejects.toBeInstanceOf(OfflineError)
    expect(await getMeta('sync_cursor')).toBe(500)
    expect(await pull(server)).toBe(700)
    expect((await allEvents()).length).toBe(1200)
    expect(await getMeta('sync_cursor')).toBe(1200)
  })

  it('a pulled copy of an event we never heard was uploaded marks it synced', async () => {
    const [e] = device('phone', 1)
    await mergeEvents([e!]) // unsynced locally...
    server.log = [e!] // ...but the server stored it before the response was lost
    await pull(server)
    expect(await countEvents()).toEqual({ total: 1, unsynced: 0 })
  })

  it('caches quest plans for today and the next two days', async () => {
    const report = await runSync(server, { today: '2026-11-04' })
    expect(report.plans).toBe(3)
    for (const day of ['2026-11-04', '2026-11-05', '2026-11-06']) {
      expect((await getCache<QuestPlan>(questPlanKey(day)))?.day).toBe(day)
    }
    // A later sync from another day overwrites with the server's fixed plan, doesn't drop any.
    await setCache(questPlanKey('2026-11-05'), { day: '2026-11-05', items: [] })
    await runSync(server, { today: '2026-11-05' })
    expect((await getCache<QuestPlan>(questPlanKey('2026-11-05')))?.items).toEqual([[0, 'ex-0']])
    expect(await getCache(questPlanKey('2026-11-04'))).toBeDefined()
  })

  it('a step waiting on a TODO(me) is reported; the others still run', async () => {
    await mergeEvents(device('phone', 2))
    server.locked = new Set(['post', 'get', 'quests'])
    const r = await runSync(server, { today: '2026-11-04' })
    expect(r.complete).toBe(false)
    expect(r.locked.map((m) => /TODO\(me\) (\S+?):?(\s|$)/.exec(m)?.[1])).toEqual([
      'M2.5-1',
      'M2.5-2',
      'M2-2',
    ])
    expect((await countEvents()).unsynced).toBe(2) // kept for when ingestion lands
    expect(await getMeta('last_sync_at')).toBeUndefined()
    expect(await getCache('bundle')).toBeDefined() // the bundle still refreshed
  })

  it('records a full sync time only when both directions went through', async () => {
    const r = await runSync(server, { today: '2026-11-04' })
    expect(r).toMatchObject({ complete: true, locked: [] })
    expect(typeof (await getMeta('last_sync_at'))).toBe('string')
  })
})
