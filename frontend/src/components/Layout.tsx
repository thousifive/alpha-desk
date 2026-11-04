import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, NavLink, Outlet } from 'react-router'

import { useLogout, useProgress } from '../api/hooks'
import { requestPersistence } from '../lib/local/persist'
import { startSync } from '../lib/sync/controller'
import { SyncPill } from './SyncPill'

const SECTIONS = [
  { to: '/', label: 'DASHBOARD', short: 'DESK', end: true },
  { to: '/branches/sql-olap', label: 'SQL & OLAP', short: 'SQL' },
  { to: '/branches/python-fastapi', label: 'PYTHON', short: 'PYTHON' },
  { to: '/branches/data-pipelines', label: 'PIPELINES', short: 'PIPES' },
] as const

export function Layout() {
  const progress = useProgress()
  const logout = useLogout()
  const qc = useQueryClient()
  const p = progress.data

  // Health checks + sync for as long as the logged-in shell is mounted.
  useEffect(() => startSync(qc), [qc])
  useEffect(() => void requestPersistence(), [])

  const navCls = ({ isActive }: { isActive: boolean }) =>
    `flex h-11 items-center px-2 rounded ${isActive ? 'text-amber' : 'text-muted hover:text-ink'}`

  return (
    // Below lg the section nav moves to a bottom tab bar (thumb reach on phones, and the
    // header row has no room for it at iPad-portrait width).
    <div className="flex min-h-dvh flex-col pb-(--tabbar-h) lg:pb-0">
      <header className="safe-x sticky top-0 z-20 border-b border-line bg-bg/95 pt-[env(safe-area-inset-top)] backdrop-blur">
        <div className="flex h-11 items-center gap-4">
          <Link
            to="/"
            className="flex h-11 shrink-0 items-center font-mono text-sm font-semibold tracking-wider text-amber"
          >
            ALPHA DESK
          </Link>
          <nav className="hidden min-w-0 gap-1 whitespace-nowrap font-mono text-xs lg:flex">
            {SECTIONS.map((s) => (
              <NavLink key={s.to} to={s.to} end={'end' in s} className={navCls}>
                {s.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex min-w-0 items-center gap-3 whitespace-nowrap font-mono text-xs">
            {p && (
              <span className="hidden text-muted sm:inline">
                <span className="text-ink">{p.level?.title ?? '—'}</span>
                <span className="mx-2 text-line">|</span>
                <span className="text-amber">{p.xp_total.toLocaleString()}</span> XP
              </span>
            )}
            <SyncPill />
            <span className="hidden items-center gap-3 lg:flex">
              <NavLink to="/settings" className={navCls}>
                SETTINGS
              </NavLink>
              <button
                onClick={() => logout.mutate()}
                className="h-11 px-1 text-muted hover:text-ink"
              >
                LOG OUT
              </button>
            </span>
          </div>
        </div>
      </header>
      <Outlet />
      <nav
        aria-label="Sections"
        className="safe-x fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-line bg-bg/95 pb-[env(safe-area-inset-bottom)] font-mono text-[10px] tracking-wider backdrop-blur lg:hidden"
      >
        {[...SECTIONS, { to: '/settings', label: 'SETTINGS', short: 'SETTINGS' }].map((s) => (
          <NavLink
            key={s.to}
            to={s.to}
            end={'end' in s}
            className={({ isActive }) =>
              `flex h-14 items-center justify-center ${isActive ? 'text-amber' : 'text-muted'}`
            }
          >
            {s.short}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
