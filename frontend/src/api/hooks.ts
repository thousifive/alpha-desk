import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api } from './client'

export const qk = {
  me: ['me'] as const,
}

/** The browser's IANA zone. "Today" for quests and streaks is computed in it server-side. */
export const browserTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone

export function useMe() {
  return useQuery({
    queryKey: qk.me,
    queryFn: async () => {
      try {
        return await api.get<{ authenticated: boolean }>('/auth/me')
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return { authenticated: false }
        throw e
      }
    },
    staleTime: Infinity,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (password: string) =>
      api.post<{ authenticated: boolean }>('/auth/login', {
        password,
        timezone: browserTimezone(),
      }),
    onSuccess: (data) => qc.setQueryData(qk.me, data),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<{ authenticated: boolean }>('/auth/logout'),
    onSuccess: () => {
      qc.clear()
      qc.setQueryData(qk.me, { authenticated: false })
    },
  })
}

// Progress-shaped data comes from the local event log (works with the server off).
export {
  getHiddenTests,
  useBranch,
  useBranches,
  useExercise,
  useProgress,
  useQuests,
  useSubmitAttempt,
} from '../lib/local/hooks'

export function useSyncTimezone() {
  return useMutation({
    mutationFn: (timezone: string) =>
      api.put<{ authenticated: boolean }>('/auth/timezone', { timezone }),
  })
}
