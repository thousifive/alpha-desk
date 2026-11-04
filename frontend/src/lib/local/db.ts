import Dexie, { type Table } from 'dexie'

import type { LogEvent } from './events'

/**
 * A stored event. `lseq` is this device's insertion order (auto-increment): the rules worker
 * is fed "everything after lseq N", and sync (Part 2) uploads rows with synced = 0.
 * IndexedDB can't index booleans, hence 0 | 1.
 */
export interface StoredEvent extends LogEvent {
  lseq?: number
  synced: 0 | 1
}

export interface KV {
  key: string
  value: unknown
  updated_at: string
}

export class AlphaDB extends Dexie {
  events!: Table<StoredEvent, number>
  cache!: Table<KV, string> // content bundle, quest plans, last snapshot: re-fetchable
  meta!: Table<KV, string> // device id, cursors, flags: not re-fetchable

  constructor(name = 'alpha-desk') {
    super(name)
    // `++lseq` = auto-increment primary key, `&id` = unique index (merge-by-id relies on it).
    this.version(1).stores({
      events: '++lseq, &id, synced, created_at',
      cache: 'key',
      meta: 'key',
    })
  }
}

let instance: AlphaDB | null = null

export function getDB(): AlphaDB {
  instance ??= new AlphaDB()
  return instance
}

/** Tests only: point the module at a fresh database. */
export function setDBForTests(db: AlphaDB | null) {
  instance = db
}
