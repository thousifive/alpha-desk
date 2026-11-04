import { todoFromMessage } from '../todos'
import type { SyncStatus } from './controller'

export function relativeTime(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000))
  if (s < 60) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 48) return `${h}h ago`
  return `${Math.round(h / 24)}d ago`
}

const plural = (n: number, one: string) => `${n.toLocaleString()} ${one}${n === 1 ? '' : 's'}`

export interface PillView {
  text: string
  tone: 'calm' | 'amber'
  title: string
}

export function pillView(s: SyncStatus, queued: number, now = Date.now()): PillView {
  const syncLock = s.locked.find((m) => m.startsWith('Sync offline'))
  if (s.syncing) return { text: 'Syncing…', tone: 'calm', title: 'Talking to the server' }
  if (s.reachability !== 'up') {
    return {
      text: queued ? `Offline · ${plural(queued, 'change')} queued` : 'Offline',
      tone: queued ? 'amber' : 'calm',
      title: 'Progress is saved on this device and syncs when the server is on.',
    }
  }
  if (syncLock) {
    const t = todoFromMessage(syncLock)
    return {
      text: `Sync locked · TODO(me) ${t?.id ?? ''}`.trim(),
      tone: 'amber',
      title: t ? `${t.fn}() in ${t.file}. ${t.story}` : syncLock,
    }
  }
  if (queued) return { text: `${plural(queued, 'change')} to sync`, tone: 'amber', title: '' }
  return {
    text: s.lastSyncAt ? `Synced · ${relativeTime(s.lastSyncAt, now)}` : 'Online',
    tone: 'calm',
    title: s.lastSyncAt ? `Last sync ${new Date(s.lastSyncAt).toLocaleString()}` : '',
  }
}
