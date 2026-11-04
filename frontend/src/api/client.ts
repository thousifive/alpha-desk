import { clearToken, getToken } from '../lib/auth/token'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** The server can't be reached at all (off, asleep, no network). Normal, not an error. */
export class OfflineError extends Error {
  constructor(cause?: unknown) {
    super('Server unreachable', { cause })
  }
}

// Empty in dev (Vite proxies /api). On Netlify: the tunnel URL, e.g. https://api.example.com.
export const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

const TIMEOUT_MS = 15_000

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api${path}`, {
      method,
      credentials: 'same-origin',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    })
  } catch (e) {
    throw new OfflineError(e) // network failure or timeout: no HTTP response at all
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data: unknown = await res.json()
      if (data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string') {
        detail = data.detail
      }
    } catch {
      /* non-JSON error body */
    }
    // The server rejected our token (expired, or SESSION_SECRET rotated): log in again.
    if (res.status === 401 && token) void clearToken()
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
}
