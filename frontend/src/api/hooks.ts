import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { clearToken, isAuthenticated, onTokenChange, setToken } from '../lib/auth/token'
import { api } from './client'

export const qk = {
  me: ['me'] as const,
}

/** The browser's IANA zone. Sent at login and on each sync, so the server's "today" matches. */
export const browserTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone

export function useMe() {
  // Decided locally from the stored token, so the app opens with the server off.
  const qc = useQueryClient()
  useEffect(
    () => onTokenChange(() => qc.setQueryData(qk.me, { authenticated: isAuthenticated() })),
    [qc],
  )
  return useQuery({
    queryKey: qk.me,
    queryFn: () => ({ authenticated: isAuthenticated() }),
    staleTime: Infinity,
  })
}

interface TokenOut {
  authenticated: boolean
  token: string
  expires_at: string
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (password: string) => {
      const res = await api.post<TokenOut>('/auth/login', { password, timezone: browserTimezone() })
      await setToken({ token: res.token, expires_at: res.expires_at })
      return { authenticated: true }
    },
    onSuccess: (data) => qc.setQueryData(qk.me, data),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      // The token is the login; dropping it logs out even with the server off. The server
      // call only clears a dev session cookie, so its failure doesn't matter.
      await clearToken()
      await api.post('/auth/logout').catch(() => undefined)
      return { authenticated: false }
    },
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
