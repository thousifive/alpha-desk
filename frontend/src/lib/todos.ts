import type { Persona } from '../api/types'

/**
 * Every TODO(me) task that gates a UI feature. One registry so locked-state copy, file paths,
 * and function names live in one place instead of being scattered across components.
 * Keep `id` identical to the marker the backend raises: `NotImplementedError("TODO(me) <id>: …")`.
 */
export interface TodoTask {
  id: string
  fn: string
  file: string
  persona: Persona
  /** In-story line from the colleague who's waiting on the PR. */
  story: string
}

export const TODOS = {
  '#1': {
    id: '#1',
    fn: 'level_for_xp',
    file: 'backend/app/game/levels.py',
    persona: 'lena',
    story: 'The level system is waiting on your PR.',
  },
  '#2': {
    id: '#2',
    fn: 'xp_for_attempt',
    file: 'backend/app/game/xp.py',
    persona: 'lena',
    story: "Payroll can't pay out XP until your PR lands.",
  },
  '#3': {
    id: '#3',
    fn: 'compare_result_sets',
    file: 'backend/app/grading/sql.py',
    persona: 'marcus',
    story: "I can't check your numbers until the result-set comparer is merged.",
  },
  'M2-1': {
    id: 'M2-1',
    fn: 'compute_streak',
    file: 'backend/app/game/streaks.py',
    persona: 'lena',
    story: 'The streak tracker is waiting on your PR.',
  },
  'M2-2': {
    id: 'M2-2',
    fn: 'weighted_sample',
    file: 'backend/app/game/quests.py',
    persona: 'priya',
    story: "I'll send today's tickets as soon as the quest picker is merged.",
  },
  'M2-3': {
    id: 'M2-3',
    fn: 'grade_python_report',
    file: 'backend/app/grading/python.py',
    persona: 'lena',
    story: "CI can't grade Python until your report checker is merged.",
  },
} as const satisfies Record<string, TodoTask>

export type TodoId = keyof typeof TODOS

/** Find which TODO(me) a backend 501 message names, e.g. "Grader offline: TODO(me) M2-3: …". */
export function todoFromMessage(message: string): TodoTask | null {
  const id = /TODO\(me\) (#\d+|M\d+-\d+)/.exec(message)?.[1]
  return id && id in TODOS ? TODOS[id as TodoId] : null
}
