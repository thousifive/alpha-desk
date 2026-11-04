import { getMeta, setMeta } from '../local/store'

// The 30-day bearer token, kept in IndexedDB (not a cookie: iOS blocks third-party cookies
// for a PWA on netlify.app calling the API on another domain). Mirrored in memory so the API
// client can attach it synchronously.

export interface StoredToken {
  token: string
  expires_at: string
}

let current: StoredToken | null = null
const listeners = new Set<() => void>()

const KEY = 'auth_token'

export async function loadToken(): Promise<void> {
  current = (await getMeta<StoredToken | null>(KEY).catch(() => null)) ?? null
}

export function getToken(): string | null {
  return current && Date.parse(current.expires_at) > Date.now() ? current.token : null
}

export function tokenExpiresAt(): number | null {
  return current ? Date.parse(current.expires_at) : null
}

/** Logged in for app purposes: holds an unexpired token. Works with the server off. */
export const isAuthenticated = () => getToken() !== null

export async function setToken(t: StoredToken | null): Promise<void> {
  current = t
  await setMeta(KEY, t)
  for (const fn of listeners) fn()
}

export const clearToken = () => setToken(null)

export function onTokenChange(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
