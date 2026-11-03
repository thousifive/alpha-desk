import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api } from './client'
import type {
  AttemptIn,
  AttemptOut,
  BranchDetail,
  BranchSummary,
  Exercise,
  Progress,
} from './types'

export const qk = {
  me: ['me'] as const,
  progress: ['progress'] as const,
  branches: ['branches'] as const,
  branch: (id: string) => ['branches', id] as const,
  exercise: (slug: string) => ['exercises', slug] as const,
}

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
      api.post<{ authenticated: boolean }>('/auth/login', { password }),
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

export const useProgress = () =>
  useQuery({ queryKey: qk.progress, queryFn: () => api.get<Progress>('/progress') })

export const useBranches = () =>
  useQuery({ queryKey: qk.branches, queryFn: () => api.get<BranchSummary[]>('/branches') })

export const useBranch = (id: string) =>
  useQuery({ queryKey: qk.branch(id), queryFn: () => api.get<BranchDetail>(`/branches/${id}`) })

export const useExercise = (slug: string) =>
  useQuery({ queryKey: qk.exercise(slug), queryFn: () => api.get<Exercise>(`/exercises/${slug}`) })

export function useSubmitAttempt(slug: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: AttemptIn) => api.post<AttemptOut>(`/exercises/${slug}/attempts`, body),
    onSuccess: (out) => {
      if (!out.passed) return
      // A pass can change XP, node states, and unlocks: refetch everything progress-shaped.
      void qc.invalidateQueries({ queryKey: qk.progress })
      void qc.invalidateQueries({ queryKey: qk.branches })
      void qc.invalidateQueries({ queryKey: ['exercises'] })
    },
  })
}
