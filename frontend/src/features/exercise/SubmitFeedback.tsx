import { motion } from 'framer-motion'
import { Link } from 'react-router'

import type { AttemptOut } from '../../api/types'

interface Props {
  out: AttemptOut
  nextSlug: string | null
  branchId: string
}

export function SubmitFeedback({ out, nextSlug, branchId }: Props) {
  const gained = out.xp_awarded + out.node_bonus_xp
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded border px-3 py-2 text-sm ${out.passed ? 'border-up/40 bg-up/10' : 'border-down/40 bg-down/10'}`}
      role="status"
    >
      <p className={`font-mono text-xs font-semibold ${out.passed ? 'text-up' : 'text-down'}`}>
        {out.passed ? 'TICKET CLOSED' : 'REOPENED'}
      </p>
      <p className="mt-1">{out.feedback}</p>
      {out.passed && (
        <p className="mt-1 font-mono text-xs text-muted">
          {out.already_passed
            ? 'Already solved, no XP this time.'
            : `+${out.xp_awarded} XP${out.node_bonus_xp ? ` · node mastered +${out.node_bonus_xp}` : ''} · total ${out.xp_total.toLocaleString()}`}
        </p>
      )}
      {out.explanation && <p className="mt-2 text-muted">{out.explanation}</p>}
      {out.passed && (
        <div className="mt-2 flex gap-3 font-mono text-xs">
          {nextSlug ? (
            <Link to={`/exercises/${nextSlug}`} className="text-amber hover:underline">
              NEXT TICKET →
            </Link>
          ) : (
            <Link to={`/branches/${branchId}`} className="text-amber hover:underline">
              BACK TO BRANCH →
            </Link>
          )}
          {gained > 0 && <span className="sr-only">Gained {gained} XP</span>}
        </div>
      )}
    </motion.div>
  )
}
