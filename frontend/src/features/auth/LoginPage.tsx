import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router'

import { ApiError } from '../../api/client'
import { useLogin, useMe } from '../../api/hooks'

export function LoginPage() {
  const me = useMe()
  const login = useLogin()
  const location = useLocation()
  const [password, setPassword] = useState('')
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (me.data?.authenticated) return <Navigate to={from} replace />

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    login.mutate(password)
  }

  const error =
    login.error instanceof ApiError && login.error.status === 401
      ? 'Access denied.'
      : login.error
        ? 'Login failed. Is the backend running?'
        : null

  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-lg border border-line bg-panel p-6"
      >
        <p className="font-mono text-xs tracking-[0.2em] text-muted">MERIDIAN CAPITAL</p>
        <h1 className="mt-1 font-mono text-2xl font-semibold text-amber">ALPHA DESK</h1>
        <p className="mt-3 text-sm text-muted">Badge in to start your shift.</p>
        <label className="mt-6 block text-xs uppercase tracking-wider text-muted" htmlFor="pw">
          Password
        </label>
        <input
          id="pw"
          type="password"
          autoFocus
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded border border-line bg-bg px-3 py-2 font-mono outline-none focus:border-amber"
        />
        {error && (
          <p className="mt-2 text-sm text-down" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={!password || login.isPending}
          className="mt-4 w-full rounded bg-amber py-2 font-mono text-sm font-semibold text-bg disabled:opacity-40"
        >
          {login.isPending ? 'CHECKING…' : 'LOG IN'}
        </button>
      </form>
    </main>
  )
}
