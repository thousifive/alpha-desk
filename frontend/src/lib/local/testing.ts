import { AlphaDB, setDBForTests } from './db'
import type { LogEvent } from './events'

let n = 0

/** A fresh, empty IndexedDB (in memory) for each test. */
export function freshDB(): AlphaDB {
  const db = new AlphaDB(`test-${++n}-${Math.random()}`)
  setDBForTests(db)
  return db
}

export function ev(i: number, over: Partial<LogEvent> = {}): LogEvent {
  return {
    id: `00000000-0000-4000-8000-${String(i).padStart(12, '0')}`,
    device_id: 'phone',
    type: 'attempt',
    payload: { exercise_slug: 'sql-first-look', passed: true, code: 'select 1' },
    created_at: `2026-11-01T0${i % 10}:00:00Z`,
    local_date: '2026-11-01',
    ...over,
  }
}
