import { Link, NavLink, Outlet } from 'react-router'

import { useLogout, useProgress } from '../api/hooks'

export function Layout() {
  const progress = useProgress()
  const logout = useLogout()
  const p = progress.data

  const navCls = ({ isActive }: { isActive: boolean }) =>
    `px-2 py-1 rounded ${isActive ? 'text-amber bg-panel-2' : 'text-muted hover:text-ink'}`

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 flex h-11 items-center gap-4 border-b border-line bg-bg/90 px-4 backdrop-blur">
        <Link to="/" className="font-mono text-sm font-semibold tracking-wider text-amber">
          ALPHA DESK
        </Link>
        <nav className="flex gap-1 font-mono text-xs">
          <NavLink to="/" end className={navCls}>
            DASHBOARD
          </NavLink>
          <NavLink to="/branches/sql-olap" className={navCls}>
            SQL &amp; OLAP
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3 font-mono text-xs">
          {p && (
            <span className="text-muted">
              <span className="text-ink">{p.level?.title ?? '—'}</span>
              <span className="mx-2 text-line">|</span>
              <span className="text-amber">{p.xp_total.toLocaleString()}</span> XP
            </span>
          )}
          <button onClick={() => logout.mutate()} className="text-muted hover:text-ink">
            LOG OUT
          </button>
        </div>
      </header>
      <Outlet />
    </div>
  )
}
