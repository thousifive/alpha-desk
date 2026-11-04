import { useEffect } from 'react'
import { Link, NavLink, Outlet } from 'react-router'

import { browserTimezone, useLogout, useProgress, useSyncTimezone } from '../api/hooks'
import { useOfflineBootstrap } from '../lib/local/hooks'

export function Layout() {
  const progress = useProgress()
  const logout = useLogout()
  const syncTz = useSyncTimezone()
  useOfflineBootstrap()
  const p = progress.data

  // Once per app load: keeps "today" right if the player travels after logging in.
  const { mutate: syncTimezone } = syncTz
  useEffect(() => syncTimezone(browserTimezone()), [syncTimezone])

  const navCls = ({ isActive }: { isActive: boolean }) =>
    `px-2 py-1 rounded ${isActive ? 'text-amber bg-panel-2' : 'text-muted hover:text-ink'}`

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 flex h-11 items-center gap-4 border-b border-line bg-bg/90 px-4 backdrop-blur">
        <Link to="/" className="shrink-0 font-mono text-sm font-semibold tracking-wider text-amber">
          ALPHA DESK
        </Link>
        <nav className="flex min-w-0 gap-1 overflow-x-auto whitespace-nowrap font-mono text-xs">
          <NavLink to="/" end className={navCls}>
            DASHBOARD
          </NavLink>
          <NavLink to="/branches/sql-olap" className={navCls}>
            SQL &amp; OLAP
          </NavLink>
          <NavLink to="/branches/python-fastapi" className={navCls}>
            PYTHON
          </NavLink>
          <NavLink to="/branches/data-pipelines" className={navCls}>
            PIPELINES
          </NavLink>
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-3 whitespace-nowrap font-mono text-xs">
          {p && (
            <span className="hidden text-muted sm:inline">
              <span className="text-ink">{p.level?.title ?? '—'}</span>
              <span className="mx-2 text-line">|</span>
              <span className="text-amber">{p.xp_total.toLocaleString()}</span> XP
            </span>
          )}
          <NavLink to="/settings" className={navCls}>
            SETTINGS
          </NavLink>
          <button onClick={() => logout.mutate()} className="text-muted hover:text-ink">
            LOG OUT
          </button>
        </div>
      </header>
      <Outlet />
    </div>
  )
}
