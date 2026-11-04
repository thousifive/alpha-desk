import { beforeEach, describe, expect, it } from 'vitest'

import * as store from './store'
import { ev, freshDB } from './testing'

describe('event store', () => {
  beforeEach(() => void freshDB())

  it('merges by id: duplicates in the batch and already-stored ids are skipped', async () => {
    expect(await store.mergeEvents([ev(1), ev(2), ev(1)])).toBe(2)
    expect(await store.mergeEvents([ev(2), ev(3)])).toBe(1)
    const all = await store.allEvents()
    expect(all.map((e) => e.id)).toEqual([ev(1).id, ev(2).id, ev(3).id])
  })

  it('assigns increasing lseq so the rules worker can be fed incrementally', async () => {
    await store.mergeEvents([ev(1), ev(2)])
    const [a, b] = await store.allEvents()
    expect(a!.lseq! < b!.lseq!).toBe(true)
    expect((await store.eventsAfter(a!.lseq!)).map((e) => e.id)).toEqual([ev(2).id])
  })

  it('tracks unsynced events; server-originated ones arrive synced', async () => {
    await store.mergeEvents([ev(1), ev(2)])
    await store.mergeEvents([ev(3)], { synced: true })
    expect(await store.countEvents()).toEqual({ total: 3, unsynced: 2 })
  })

  it('keeps one device id per database', async () => {
    const a = await store.getDeviceId()
    expect(await store.getDeviceId()).toBe(a)
    freshDB()
    expect(await store.getDeviceId()).not.toBe(a)
  })

  it('notifies listeners only when something new was stored', async () => {
    let calls = 0
    const off = store.onLogChange(() => calls++)
    await store.mergeEvents([ev(1)])
    await store.mergeEvents([ev(1)])
    off()
    expect(calls).toBe(1)
  })

  it('exposes no way to update or delete events', () => {
    const names = Object.keys(store)
    expect(names.some((n) => /delete|remove|clear|update/i.test(n))).toBe(false)
  })
})
