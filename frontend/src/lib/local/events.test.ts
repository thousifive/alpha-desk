import { describe, expect, it } from 'vitest'

import { isLogEvent, localDate } from './events'
import { ev } from './testing'

describe('localDate', () => {
  it('uses the zone, not UTC: 19:00Z is already tomorrow in Kolkata (+05:30)', () => {
    const at = new Date('2026-11-02T19:00:00Z')
    expect(localDate(at, 'Asia/Kolkata')).toBe('2026-11-03')
    expect(localDate(at, 'UTC')).toBe('2026-11-02')
  })
})

describe('isLogEvent', () => {
  it('accepts a well-formed event and rejects junk', () => {
    expect(isLogEvent(ev(1))).toBe(true)
    expect(isLogEvent({ ...ev(1), type: 'nope' })).toBe(false)
    expect(isLogEvent({ ...ev(1), id: '1' })).toBe(false)
    expect(isLogEvent(null)).toBe(false)
  })
})
