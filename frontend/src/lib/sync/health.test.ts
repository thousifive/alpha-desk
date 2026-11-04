import { describe, expect, it } from 'vitest'

import { DOWN_BASE_MS, DOWN_MAX_MS, HealthMonitor, UP_INTERVAL_MS } from './health'

function setup(results: boolean[], visible = true) {
  const timers: number[] = []
  const pings: boolean[] = [...results]
  const m = new HealthMonitor({
    ping: async () => pings.shift() ?? false,
    isVisible: () => visible,
    setTimer: (_fn, ms) => timers.push(ms),
    clearTimer: () => undefined,
  })
  return { m, timers }
}

describe('HealthMonitor', () => {
  it('polls every 60 s while up', async () => {
    const { m, timers } = setup([true, true])
    expect(await m.check()).toBe('up')
    expect(timers.at(-1)).toBe(UP_INTERVAL_MS)
  })

  it('backs off exponentially while down, capped at 5 minutes', async () => {
    const { m, timers } = setup([])
    for (let i = 0; i < 8; i++) await m.check()
    expect(timers).toEqual([
      DOWN_BASE_MS,
      DOWN_BASE_MS * 2,
      DOWN_BASE_MS * 4,
      DOWN_BASE_MS * 8,
      DOWN_BASE_MS * 16,
      DOWN_MAX_MS,
      DOWN_MAX_MS,
      DOWN_MAX_MS,
    ])
  })

  it('resets the backoff once the server answers', async () => {
    const { m, timers } = setup([false, false, true, false])
    for (let i = 0; i < 4; i++) await m.check()
    expect(timers).toEqual([DOWN_BASE_MS, DOWN_BASE_MS * 2, UP_INTERVAL_MS, DOWN_BASE_MS])
  })

  it('notifies only on changes and does not poll hidden tabs', async () => {
    const { m, timers } = setup([false, false, true], false)
    const seen: string[] = []
    m.subscribe((s) => seen.push(s))
    await m.check()
    await m.check()
    await m.check()
    expect(seen).toEqual(['down', 'up'])
    expect(timers).toEqual([])
  })

  it('coalesces concurrent checks into one ping', async () => {
    let pings = 0
    const m = new HealthMonitor({
      ping: async () => (pings++, true),
      isVisible: () => true,
      setTimer: () => 0,
      clearTimer: () => undefined,
    })
    await Promise.all([m.check(), m.check(), m.check()])
    expect(pings).toBe(1)
  })
})
