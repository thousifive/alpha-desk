import { describe, expect, it } from 'vitest'

import type { SyncStatus } from './controller'
import { pillView, relativeTime } from './pill'

const NOW = Date.parse('2026-11-04T12:00:00Z')
const base: SyncStatus = { reachability: 'up', syncing: false, lastSyncAt: null, locked: [] }

describe('sync pill', () => {
  it('formats relative times', () => {
    expect(relativeTime('2026-11-04T11:59:30Z', NOW)).toBe('just now')
    expect(relativeTime('2026-11-04T11:15:00Z', NOW)).toBe('45m ago')
    expect(relativeTime('2026-11-04T10:00:00Z', NOW)).toBe('2h ago')
    expect(relativeTime('2026-11-01T12:00:00Z', NOW)).toBe('3d ago')
  })

  it('shows synced, offline with a queue, and syncing', () => {
    expect(pillView({ ...base, lastSyncAt: '2026-11-04T10:00:00Z' }, 0, NOW).text).toBe(
      'Synced · 2h ago',
    )
    const off = pillView({ ...base, reachability: 'down' }, 14, NOW)
    expect(off).toMatchObject({
      text: 'Offline · 14 changes queued',
      short: 'Offline · 14',
      tone: 'amber',
    })
    expect(pillView({ ...base, reachability: 'down' }, 1, NOW).text).toBe(
      'Offline · 1 change queued',
    )
    expect(pillView({ ...base, reachability: 'down' }, 0, NOW)).toMatchObject({
      text: 'Offline · server not reachable (is Tailscale on?)',
      short: 'Offline',
      tone: 'calm',
    })
    expect(off.title).toContain('Tailscale')
    expect(pillView({ ...base, syncing: true }, 3, NOW).text).toBe('Syncing…')
  })

  it('names the TODO(me) holding sync back, but not the quest planner', () => {
    const v = pillView({ ...base, locked: ['Sync offline: TODO(me) M2.5-1: implement x'] }, 2, NOW)
    expect(v).toMatchObject({ text: 'Sync locked · TODO(me) M2.5-1', tone: 'amber' })
    expect(v.title).toContain('ingest_events')
    const quests = pillView({ ...base, locked: ['Quest board offline: TODO(me) M2-2: x'] }, 0, NOW)
    expect(quests.text).toBe('Online')
  })
})
