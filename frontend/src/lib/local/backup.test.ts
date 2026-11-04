import { beforeEach, describe, expect, it } from 'vitest'

import { BackupFormatError, buildBackup, importBackup, parseBackup } from './backup'
import { allEvents, mergeEvents } from './store'
import { ev, freshDB } from './testing'

describe('export / import', () => {
  beforeEach(() => void freshDB())

  it('round-trips the whole log into an empty device', async () => {
    await mergeEvents([
      ev(1),
      ev(2, { type: 'xp_awarded', payload: { ref_key: 'k', source: 'attempt', amount: 5 } }),
    ])
    const text = JSON.stringify(await buildBackup())
    const before = (await allEvents()).map(({ lseq: _l, ...e }) => e)

    freshDB() // "iOS cleared the site data"
    expect(await importBackup(text)).toEqual({ added: 2, skipped: 0, invalid: 0 })
    const after = (await allEvents()).map(({ lseq: _l, ...e }) => e)
    // Restored events are unsynced again: harmless, the server dedupes by id.
    expect(after).toEqual(before.map((e) => ({ ...e, synced: 0 })))
  })

  it('importing twice adds nothing the second time', async () => {
    await mergeEvents([ev(1)])
    const text = JSON.stringify(await buildBackup())
    expect(await importBackup(text)).toEqual({ added: 0, skipped: 1, invalid: 0 })
  })

  it('merges with what the device already has', async () => {
    await mergeEvents([ev(1)])
    const text = JSON.stringify(await buildBackup())
    freshDB()
    await mergeEvents([ev(2)])
    await importBackup(text)
    expect((await allEvents()).map((e) => e.id).sort()).toEqual([ev(1).id, ev(2).id])
  })

  it('rejects foreign files and counts malformed entries', async () => {
    expect(() => parseBackup('nope')).toThrow(BackupFormatError)
    expect(() => parseBackup('{"format":"something-else","events":[]}')).toThrow(BackupFormatError)
    const text = JSON.stringify({
      format: 'alpha-desk/events',
      version: 1,
      events: [ev(1), { id: 'x' }, { ...ev(2), local_date: 'Nov 1' }],
    })
    expect(await importBackup(text)).toEqual({ added: 1, skipped: 0, invalid: 2 })
  })
})
