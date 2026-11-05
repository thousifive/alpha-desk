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
  /** Phone header: the same state in a few characters. */
  short: string
  tone: 'calm' | 'amber'
  title: string
}

export const OFFLINE_TITLE =
  'Server not reachable (is Tailscale on? is the server running?). Progress is saved on this device and syncs when it is back.'

export function pillView(s: SyncStatus, queued: number, now = Date.now()): PillView {
  const syncLock = s.locked.find((m) => m.startsWith('Sync offline'))
  if (s.syncing) {
    return { text: 'Syncing…', short: 'Syncing…', tone: 'calm', title: 'Talking to the server' }
  }
  if (s.reachability !== 'up') {
    // The server is private to the tailnet, so "unreachable" is usually Tailscale being off
    // on this device (or the server not running). Both look the same from here.
    return {
      text: queued
        ? `Offline · ${plural(queued, 'change')} queued`
        : 'Offline · server not reachable (is Tailscale on?)',
      short: queued ? `Offline · ${queued.toLocaleString()}` : 'Offline',
      tone: queued ? 'amber' : 'calm',
      title: OFFLINE_TITLE,
    }
  }
  if (syncLock) {
    const t = todoFromMessage(syncLock)
    return {
      text: `Sync locked · TODO(me) ${t?.id ?? ''}`.trim(),
      short: 'Sync locked',
      tone: 'amber',
      title: t ? `${t.fn}() in ${t.file}. ${t.story}` : syncLock,
    }
  }
  if (queued) {
    const text = `${plural(queued, 'change')} to sync`
    return { text, short: `${queued.toLocaleString()} to sync`, tone: 'amber', title: '' }
  }
  return {
    text: s.lastSyncAt ? `Synced · ${relativeTime(s.lastSyncAt, now)}` : 'Online',
    short: s.lastSyncAt ? `Synced ${relativeTime(s.lastSyncAt, now)}` : 'Online',
    tone: 'calm',
    title: s.lastSyncAt ? `Last sync ${new Date(s.lastSyncAt).toLocaleString()}` : '',
  }
}
