import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { ApiError, api } from '../../api/client'
import type { AttemptIn, AttemptOut, QuestBoard } from '../../api/types'
import { getEngine, NoBundleError, type Bundle, type QuestPlan, type Snapshot } from './engine'
import { localDate, type LogEvent } from './events'
import { requestPersistence } from './persist'
import {
  getCache,
  getDeviceId,
  getMeta,
  mergeEvents,
  onLogChange,
  setCache,
  setMeta,
} from './store'

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
  }
}

const planKey = (day: string) => `quest_plan:${day}`

async function todaysPlan(day: string): Promise<QuestPlan> {
  const cached = await getCache<QuestPlan>(planKey(day))
  if (cached) return cached
  let board: QuestBoard
  try {
    board = await api.get<QuestBoard>('/quests/today')
  } catch (e) {
    if (e instanceof ApiError && e.status === 501) throw e // locked TODO(me): keep the id
    throw new NoQuestPlanError()
  }
  // Only the plan (which exercise in which slot) comes from the server; completion is derived
  // from the local log, so quests closed offline stay closed.
  const plan: QuestPlan = { day: board.day, items: board.items.map((i) => [i.position, i.slug]) }
  await setCache(planKey(board.day), plan)
  if (board.day !== day) throw new NoQuestPlanError()
  return plan
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
      const plan = await getCache<QuestPlan>(planKey(today))
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

// ---- bootstrap ------------------------------------------------------------------------

/**
 * While the server is reachable: refresh the content bundle and, once per device, import the
 * progress recorded before the event log existed. Failures are silent: offline is normal.
 */
export function useOfflineBootstrap() {
  const qc = useQueryClient()
  return useQuery({
    queryKey: ['bootstrap'],
    queryFn: async () => {
      void requestPersistence()
      const bundle = await api.get<Bundle>('/offline/bundle')
      const current = await getCache<Bundle>('bundle')
      if (current?.version !== bundle.version) {
        await setCache('bundle', bundle)
        void qc.invalidateQueries({ queryKey: lk.all })
      }
      if (!(await getMeta<boolean>('legacy_imported'))) {
        const legacy = await api.get<LogEvent[]>('/offline/legacy-events')
        // Marked synced: they came *from* the server, there's nothing to upload.
        await mergeEvents(legacy, { synced: true })
        await setMeta('legacy_imported', true)
      }
      return bundle.version
    },
    staleTime: 5 * 60_000,
    retry: false,
  })
}
