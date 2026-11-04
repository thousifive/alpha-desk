import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { ApiError } from '../../api/client'
import type { AttemptIn, AttemptOut } from '../../api/types'
import { getSyncStatus } from '../sync/controller'
import { getEngine, NoBundleError, questPlanKey, type QuestPlan, type Snapshot } from './engine'
import { localDate } from './events'
import { getCache, getDeviceId, mergeEvents, onLogChange, setCache } from './store'

// Progress hooks backed by the local event log. They return the same shapes the old
// server-backed hooks did, so screens don't care where the numbers come from.

export const lk = {
  all: ['local'] as const,
  snapshot: (day: string) => ['local', 'snapshot', day] as const,
  exercise: (slug: string) => ['local', 'exercise', slug] as const,
  quests: (day: string) => ['local', 'quests', day] as const,
}

/** Recompute every local view whenever the event log or the bundle changes (in any tab). */
export function wireLocalInvalidation(qc: QueryClient): () => void {
  return onLogChange(() => void qc.invalidateQueries({ queryKey: lk.all }))
}

/** Paint the last computed dashboard instantly while the rules worker boots (~2-4 s on iOS). */
export async function primeSnapshot(qc: QueryClient): Promise<void> {
  const snap = await getCache<Snapshot>('snapshot').catch(() => undefined)
  // updatedAt: 0 marks it stale, so it's shown immediately *and* recomputed on mount.
  if (snap) qc.setQueryData(lk.snapshot(localDate()), snap, { updatedAt: 0 })
}

function useSnapshot<T>(select: (s: Snapshot) => T) {
  const day = localDate()
  return useQuery({
    queryKey: lk.snapshot(day),
    queryFn: async () => {
      const snap = await getEngine().snapshot(day)
      void setCache('snapshot', snap)
      return snap
    },
    select,
    retry: (n, e) => !(e instanceof NoBundleError) && n < 2,
  })
}

export const useProgress = () => useSnapshot((s) => s.progress)
export const useBranches = () => useSnapshot((s) => s.branches)

export function useBranch(id: string) {
  return useSnapshot((s) => {
    const d = s.details[id]
    if (!d) throw new ApiError(404, 'Unknown branch')
    return d
  })
}

export function useExercise(slug: string) {
  return useQuery({
    queryKey: lk.exercise(slug),
    queryFn: async () => {
      const ex = await getEngine().exercise(slug)
      if (!ex) throw new ApiError(404, 'Unknown exercise')
      return ex
    },
  })
}

// ---- quests ---------------------------------------------------------------------------

export class NoQuestPlanError extends Error {
  constructor() {
    super("Priya hasn't sent today's tickets yet. They arrive the next time the server is on.")
    this.name = 'NoQuestPlanError'
  }
}

async function todaysPlan(day: string): Promise<QuestPlan> {
  // Plans arrive with each sync, three days ahead (GET /sync/quests), so this is a cache read.
  const cached = await getCache<QuestPlan>(questPlanKey(day))
  if (cached) return cached
  // The planner is a TODO(me): surface its 501 so the board shows which task unlocks it.
  const lock = getSyncStatus().locked.find((m) => m.startsWith('Quest board offline'))
  if (lock) throw new ApiError(501, lock)
  throw new NoQuestPlanError()
}

export function useQuests() {
  const day = localDate()
  return useQuery({
    queryKey: lk.quests(day),
    queryFn: async () => getEngine().quests(await todaysPlan(day)),
    retry: false,
  })
}

// ---- submit ---------------------------------------------------------------------------

async function sqlExpected(solution: string) {
  // Lazy import: DuckDB-WASM is only on the exercise route, keep it out of the main chunk.
  const { runQuery } = await import('../duckdb/db')
  const r = await runQuery(solution)
  return { columns: r.columns, rows: r.rows }
}

/** Hidden Python tests, read from the local bundle (works offline). */
export async function getHiddenTests(slug: string): Promise<string> {
  const inputs = await getEngine().gradingInputs(slug)
  if (!inputs?.hidden_tests) throw new ApiError(404, 'No tests for this exercise')
  return inputs.hidden_tests
}

export function useSubmitAttempt(slug: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (attempt: AttemptIn): Promise<AttemptOut> => {
      const engine = getEngine()
      const today = localDate()
      const inputs = await engine.gradingInputs(slug)
      const expected = inputs?.solution_sql ? await sqlExpected(inputs.solution_sql) : undefined
      const plan = await getCache<QuestPlan>(questPlanKey(today))
      const res = await engine.submit({
        slug,
        attempt,
        expected,
        device_id: await getDeviceId(),
        now: new Date().toISOString(),
        today,
        quest_plan: plan?.items ?? null,
      })
      // Same error contract as the old server route, so useSubmission's locked UI just works.
      if (res.status === 'locked') throw new ApiError(501, res.message)
      if (res.status === 'rejected') throw new ApiError(422, res.message)
      await mergeEvents(res.events)
      return res.out
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: lk.all }),
  })
}
