import { describe, expect, it } from 'vitest'

import { matchHotkey } from './keyboard'

const ev = (o: Partial<KeyboardEvent>) => ({
  key: 'Enter',
  metaKey: false,
  ctrlKey: false,
  shiftKey: false,
  ...o,
})

describe('matchHotkey', () => {
  it('Cmd/Ctrl+Enter runs', () => {
    expect(matchHotkey(ev({ metaKey: true }))).toBe('run')
    expect(matchHotkey(ev({ ctrlKey: true }))).toBe('run')
  })
  it('Cmd/Ctrl+Shift+Enter submits', () => {
    expect(matchHotkey(ev({ metaKey: true, shiftKey: true }))).toBe('submit')
  })
  it('ignores plain Enter and other keys', () => {
    expect(matchHotkey(ev({}))).toBeNull()
    expect(matchHotkey(ev({ key: 'a', metaKey: true }))).toBeNull()
  })
})
