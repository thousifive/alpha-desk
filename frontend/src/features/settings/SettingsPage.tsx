import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { Panel } from '../../components/ui'
import { BackupFormatError, downloadBackup, importBackup } from '../../lib/local/backup'
import { countEvents, getDeviceId, getMeta } from '../../lib/local/store'
import { syncNow } from '../../lib/sync/controller'
import { useSyncStatus } from '../../lib/sync/hooks'
import { relativeTime } from '../../lib/sync/pill'
import { useLogout } from '../../api/hooks'
import { todoFromMessage } from '../../lib/todos'

const EXPORT_REMINDER_DAYS = 14

function useStorageInfo() {
  // Under the 'local' key, so it refreshes with every log change (wireLocalInvalidation).
  return useQuery({
    queryKey: ['local', 'storage-info'],
    queryFn: async () => ({
      ...(await countEvents()),
      device: await getDeviceId(),
      persisted: await getMeta<boolean>('persisted'),
      lastExport: await getMeta<string>('last_export_at'),
      cursor: (await getMeta<number>('sync_cursor')) ?? 0,
      rejected: (await getMeta<number>('sync_rejected')) ?? 0,
    }),
  })
}

function daysSince(iso: string | undefined): number | null {
  return iso ? Math.floor((Date.now() - Date.parse(iso)) / 86_400_000) : null
}

export function SettingsPage() {
  const info = useStorageInfo()
  const qc = useQueryClient()
  const file = useRef<HTMLInputElement>(null)
  const [note, setNote] = useState<{ tone: 'ok' | 'warn'; text: string } | null>(null)

  const onExport = async () => {
    const n = await downloadBackup()
    setNote({ tone: 'ok', text: `Exported ${n.toLocaleString()} events.` })
    void qc.invalidateQueries({ queryKey: ['local', 'storage-info'] })
  }

  const onImport = async (f: File | undefined) => {
    if (!f) return
    try {
      const r = await importBackup(await f.text())
      const extra = r.invalid ? ` ${r.invalid} malformed entries ignored.` : ''
      setNote({
        tone: 'ok',
        text: `Imported ${r.added} new events, ${r.skipped} already here.${extra}`,
      })
    } catch (e) {
      const text = e instanceof BackupFormatError ? e.message : `Import failed: ${String(e)}`
      setNote({ tone: 'warn', text })
    } finally {
      if (file.current) file.current.value = '' // allow re-picking the same file
    }
  }

  const d = info.data
  const since = daysSince(d?.lastExport)
  const remind = d && d.total > 0 && (since === null || since >= EXPORT_REMINDER_DAYS)

  return (
    <main className="mx-auto grid w-full max-w-2xl gap-4 p-4 md:p-6">
      <Panel title="MY PROGRESS">
        <p className="text-sm text-muted">
          Progress lives on this device as an event log and syncs when the server is on. Export it
          now and then: iOS can clear site data after long inactivity.
        </p>
        {d && (
          <dl className="mt-4 grid grid-cols-2 gap-y-1.5 font-mono text-xs">
            <dt className="text-muted">Events on this device</dt>
            <dd className="text-right">{d.total.toLocaleString()}</dd>
            <dt className="text-muted">Not yet synced</dt>
            <dd className="text-right">{d.unsynced.toLocaleString()}</dd>
            <dt className="text-muted">Persistent storage</dt>
            <dd className="text-right">
              {d.persisted ? 'granted' : d.persisted === false ? 'not granted' : 'unknown'}
            </dd>
            <dt className="text-muted">Last export</dt>
            <dd className="text-right">
              {since === null ? 'never' : since === 0 ? 'today' : `${since} days ago`}
            </dd>
            <dt className="text-muted">Device id</dt>
            <dd className="truncate text-right text-muted">{d.device.slice(0, 8)}</dd>
          </dl>
        )}
        {remind && (
          <p className="mt-3 rounded border border-amber/30 bg-amber/5 p-2 text-xs text-amber">
            Time for a backup: export your progress.
          </p>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => void onExport()}
            className="min-h-11 rounded bg-amber px-4 font-mono text-xs font-semibold text-bg"
          >
            EXPORT MY PROGRESS
          </button>
          <button
            onClick={() => file.current?.click()}
            className="min-h-11 rounded border border-line px-4 font-mono text-xs text-ink hover:bg-panel-2"
          >
            IMPORT…
          </button>
          <input
            ref={file}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => void onImport(e.target.files?.[0])}
          />
        </div>
        {note && (
          <p
            role="status"
            className={`mt-3 font-mono text-xs ${note.tone === 'ok' ? 'text-up' : 'text-amber'}`}
          >
            {note.text}
          </p>
        )}
      </Panel>
      <SyncPanel cursor={d?.cursor ?? 0} rejected={d?.rejected ?? 0} />
      <AccountPanel />
    </main>
  )
}

function SyncPanel({ cursor, rejected }: { cursor: number; rejected: number }) {
  const s = useSyncStatus()
  const online = s.reachability === 'up'
  return (
    <Panel title="SYNC">
      <dl className="grid grid-cols-2 gap-y-1.5 font-mono text-xs">
        <dt className="text-muted">Server</dt>
        <dd className="text-right">
          {online ? 'on' : s.reachability === 'down' ? 'off / unreachable' : 'checking…'}
        </dd>
        <dt className="text-muted">Last full sync</dt>
        <dd className="text-right">{s.lastSyncAt ? relativeTime(s.lastSyncAt) : 'never'}</dd>
        <dt className="text-muted">Server cursor</dt>
        <dd className="text-right">{cursor}</dd>
        {rejected > 0 && (
          <>
            <dt className="text-muted">Rejected by server</dt>
            <dd className="text-right text-amber">{rejected}</dd>
          </>
        )}
      </dl>
      {s.locked.map((m) => {
        const t = todoFromMessage(m)
        return (
          <p
            key={m}
            className="mt-3 rounded border border-amber/30 bg-amber/5 p-2 text-xs text-amber"
          >
            {t ? `Waiting on TODO(me) ${t.id}: ${t.fn}() in ${t.file}` : m}
          </p>
        )
      })}
      <button
        onClick={() => void syncNow()}
        disabled={!online || s.syncing}
        className="mt-4 min-h-11 rounded border border-line px-4 font-mono text-xs text-ink hover:bg-panel-2 disabled:opacity-40"
      >
        {s.syncing ? 'SYNCING…' : 'SYNC NOW'}
      </button>
    </Panel>
  )
}

function AccountPanel() {
  const logout = useLogout()
  return (
    <Panel title="ACCOUNT">
      <p className="text-sm text-muted">
        Logging out removes this device&apos;s login token. Your progress stays on the device.
      </p>
      <button
        onClick={() => logout.mutate()}
        className="mt-4 min-h-11 rounded border border-line px-4 font-mono text-xs text-ink hover:bg-panel-2"
      >
        LOG OUT
      </button>
    </Panel>
  )
}
