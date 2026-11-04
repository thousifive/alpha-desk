// Event envelope. Mirrors backend/app/events/schema.py; the rules worker validates every event
// with that Pydantic model, so this side only needs the shape, not every payload rule.

export const EVENT_TYPES = [
  'attempt',
  'xp_awarded',
  'quest_completed',
  'flashcard_reviewed',
  'hint_used',
  'achievement_unlocked',
] as const
export type EventType = (typeof EVENT_TYPES)[number]

export interface LogEvent {
  id: string // uuid
  device_id: string
  type: EventType
  payload: Record<string, unknown>
  created_at: string // ISO 8601 with offset, UTC
  local_date: string // YYYY-MM-DD in the player's zone when it happened; never recomputed
  v?: number
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const DAY = /^\d{4}-\d{2}-\d{2}$/

/** Structural check for events coming from outside (imports, the server). */
export function isLogEvent(x: unknown): x is LogEvent {
  if (!x || typeof x !== 'object') return false
  const e = x as Record<string, unknown>
  return (
    typeof e.id === 'string' &&
    UUID.test(e.id) &&
    typeof e.device_id === 'string' &&
    e.device_id.length > 0 &&
    typeof e.type === 'string' &&
    (EVENT_TYPES as readonly string[]).includes(e.type) &&
    !!e.payload &&
    typeof e.payload === 'object' &&
    typeof e.created_at === 'string' &&
    !Number.isNaN(Date.parse(e.created_at)) &&
    typeof e.local_date === 'string' &&
    DAY.test(e.local_date)
  )
}

/** The calendar day at `at` in `timeZone` (default: this device's zone), as YYYY-MM-DD. */
export function localDate(at: Date = new Date(), timeZone?: string): string {
  // en-CA formats dates as YYYY-MM-DD, which saves assembling the parts by hand.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(at)
}
