import { isLogEvent, type LogEvent } from './events'
import { allEvents, getDeviceId, mergeEvents, setMeta } from './store'

// Manual backup: iOS may clear a site's storage after long inactivity, even when persistent
// storage was granted. The export is the full event log; import merges by event id, so
// importing the same file twice (or into a device that already has some events) is harmless.

export const BACKUP_FORMAT = 'alpha-desk/events'

export interface Backup {
  format: typeof BACKUP_FORMAT
  version: 1
  exported_at: string
  device_id: string
  events: LogEvent[]
}

export async function buildBackup(): Promise<Backup> {
  const events = (await allEvents()).map(
    ({ id, device_id, type, payload, created_at, local_date, v }): LogEvent => ({
      id,
      device_id,
      type,
      payload,
      created_at,
      local_date,
      v,
    }),
  )
  return {
    format: BACKUP_FORMAT,
    version: 1,
    exported_at: new Date().toISOString(),
    device_id: await getDeviceId(),
    events,
  }
}

/** Trigger a JSON download of the whole log. */
export async function downloadBackup(): Promise<number> {
  const backup = await buildBackup()
  const blob = new Blob([JSON.stringify(backup)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `alpha-desk-progress-${backup.exported_at.slice(0, 10)}.json`
  a.click()
  // Revoke on the next tick: Safari cancels the download if the URL dies synchronously.
  setTimeout(() => URL.revokeObjectURL(url), 0)
  await setMeta('last_export_at', backup.exported_at)
  return backup.events.length
}

export class BackupFormatError extends Error {}

export function parseBackup(text: string): LogEvent[] {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new BackupFormatError('Not a JSON file.')
  }
  if (!data || typeof data !== 'object' || (data as Backup).format !== BACKUP_FORMAT) {
    throw new BackupFormatError("This isn't an Alpha Desk progress export.")
  }
  const events = (data as Backup).events
  if (!Array.isArray(events)) throw new BackupFormatError('The export has no event list.')
  return events.filter(isLogEvent)
}

export interface ImportResult {
  added: number
  skipped: number // already on this device
  invalid: number // malformed entries, ignored
}

export async function importBackup(text: string): Promise<ImportResult> {
  const raw = (JSON.parse(text) as { events?: unknown[] }).events ?? []
  const valid = parseBackup(text)
  // Imported events count as unsynced: if they came from a device that never synced, the
  // server hasn't seen them. Re-uploading known ones is harmless (ingestion dedupes by id).
  const added = await mergeEvents(valid)
  return { added, skipped: valid.length - added, invalid: raw.length - valid.length }
}
