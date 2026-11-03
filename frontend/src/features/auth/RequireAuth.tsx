import { Navigate, Outlet, useLocation } from 'react-router'

import { useMe } from '../../api/hooks'

export function RequireAuth() {
  const me = useMe()
  const location = useLocation()
  if (me.isPending) return null
  if (!me.data?.authenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
