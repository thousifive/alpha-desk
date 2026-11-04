import { useQuery } from '@tanstack/react-query'
import { useSyncExternalStore } from 'react'

import { countEvents } from '../local/store'
import { getSyncStatus, subscribeSyncStatus, type SyncStatus } from './controller'

export function useSyncStatus(): SyncStatus {
  return useSyncExternalStore(subscribeSyncStatus, getSyncStatus)
}

/** Server reachable right now? Gate AI features (hints, PM Chat, grading) on this. */
export const useServerOnline = () => useSyncStatus().reachability === 'up'

export function useQueuedCount(): number {
  // Under 'local', so it refreshes on every log change (wireLocalInvalidation).
  return useQuery({ queryKey: ['local', 'queued'], queryFn: countEvents }).data?.unsynced ?? 0
}
