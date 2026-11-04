import { useCallback, useState } from 'react'

import { ApiError } from '../../api/client'
import { useSubmitAttempt } from '../../api/hooks'
import type { AttemptIn, AttemptOut, Exercise, Level } from '../../api/types'
import { LevelUpModal } from '../../components/LevelUpModal'
import { XpPop } from '../../components/XpPop'
import type { QueryResult } from '../../lib/duckdb/db'
import { todoFromMessage } from '../../lib/todos'

/** Everything one attempt paid: exercise, node mastery, quests, and streak milestone. */
export const totalGain = (o: AttemptOut) =>
  o.xp_awarded + o.node_bonus_xp + o.quest_xp + o.streak_xp

/** Shared submit plumbing: XP pop, level-up detection, locked state for 501 TODO(me)s. */
export function useSubmission(ex: Exercise) {
  const submit = useSubmitAttempt(ex.slug)
  const [out, setOut] = useState<AttemptOut | null>(null)
  const [levelUp, setLevelUp] = useState<Level | null>(null)
  const [popId, setPopId] = useState(0)
  const [startedAt] = useState(() => performance.now())

  const send = useCallback(
    async (body: {
      code: string
      result?: QueryResult
      choice?: number
      tests?: AttemptIn['tests']
    }) => {
      const res = await submit.mutateAsync({
        code: body.code,
        result: body.result && { columns: body.result.columns, rows: body.result.rows },
        choice: body.choice,
        tests: body.tests,
        duration_ms: Math.round(performance.now() - startedAt),
      })
      setOut(res)
      if (res.passed && totalGain(res) > 0) setPopId((n) => n + 1)
      if (res.level_before && res.level_after && res.level_after.index > res.level_before.index) {
        setLevelUp(res.level_after)
      }
    },
    [submit, startedAt],
  )

  // A 501 names the TODO(me) that blocks grading: an expected locked state, not an error.
  const locked =
    submit.error instanceof ApiError && submit.error.status === 501
      ? todoFromMessage(submit.error.message)
      : null
  const error = locked
    ? null
    : submit.error instanceof ApiError
      ? submit.error.message
      : submit.error
        ? String(submit.error)
        : null

  const pop = out && out.passed ? totalGain(out) : 0
  const overlay = (
    <>
      <XpPop id={popId} amount={pop} />
      <LevelUpModal level={levelUp} onClose={() => setLevelUp(null)} />
    </>
  )
  return { send, out, error, locked, pending: submit.isPending, overlay }
}
