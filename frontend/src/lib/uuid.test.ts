import { describe, expect, it } from 'vitest'
import { uuid } from './uuid'

const V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

describe('uuid', () => {
  it('uses randomUUID when the context has it', () => {
    expect(uuid({ randomUUID: () => 'a-b-c-d-e', getRandomValues: (a) => a })).toBe('a-b-c-d-e')
  })

  it('falls back to getRandomValues on insecure origins (LAN http)', () => {
    const insecure = { getRandomValues: crypto.getRandomValues.bind(crypto) }
    const ids = new Set(Array.from({ length: 50 }, () => uuid(insecure)))
    expect(ids.size).toBe(50)
    for (const id of ids) expect(id).toMatch(V4)
  })
})
