import { useEffect, useSyncExternalStore } from 'react'

import { getPyodide, type EngineStatus } from './client'

/** Engine status, and boots the worker on mount so it's warm by the time you hit Run. */
export function usePyodide(): EngineStatus {
  const client = getPyodide()
  const status = useSyncExternalStore(
    (cb) => client.subscribe(cb),
    () => client.status,
  )
  useEffect(() => {
    client.init().catch(() => undefined) // error state is surfaced through `status`
  }, [client])
  return status
}
