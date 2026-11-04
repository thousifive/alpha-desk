import { motion } from 'framer-motion'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../../api/client'
import { useQuests } from '../../api/hooks'
import type { QuestBoard as Board, QuestItem } from '../../api/types'
import { Locked } from '../../components/Locked'
import { Bar, Panel } from '../../components/ui'
import { NoQuestPlanError } from '../../lib/local/hooks'
import { PERSONAS } from '../../lib/personas'
import { TODOS, todoFromMessage } from '../../lib/todos'

export function QuestBoard({ fallback }: { fallback: ReactNode }) {
  const q = useQuests()

  if (q.isPending) {
    return (
      <Panel title="TODAY'S QUESTS" className="md:col-span-2">
        <p className="text-sm text-muted">Pulling today's tickets…</p>
      </Panel>
    )
  }
  if (q.isError) {
    const locked =
      q.error instanceof ApiError && q.error.status === 501
        ? (todoFromMessage(q.error.message) ?? TODOS['M2-2'])
        : null
    return (
      <Panel title="UP NEXT" className="md:col-span-2">
        {locked ? (
          <div className="mb-3">
            <Locked task={locked} />
          </div>
        ) : (
          <p className="mb-3 text-xs text-muted">
            {q.error instanceof NoQuestPlanError
              ? q.error.message
              : "Couldn't load today's quests."}
          </p>
        )}
        {fallback}
      </Panel>
    )
  }
  return <Quests board={q.data} />
}

function Quests({ board }: { board: Board }) {
  const done = board.items.filter((i) => i.completed).length
  const total = board.items.length
  return (
    <Panel
      title="TODAY'S QUESTS"
      className="md:col-span-2"
      right={
        <span className="font-mono text-[11px] text-muted">
          ~{board.est_minutes} min · +{board.xp_per_quest} XP each · +{board.all_done_bonus} for all
        </span>
      }
    >
      {total === 0 ? (
        <p className="text-sm text-muted">No open tickets to quest on. Unlock a node first.</p>
      ) : (
        <>
          <ol className="grid gap-2 sm:grid-cols-3">
            {board.items.map((it) => (
              <QuestCard key={it.position} item={it} />
            ))}
          </ol>
          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1">
              <Bar value={done / total} className={board.done ? 'bg-up' : 'bg-cyan'} />
            </div>
            <span
              className={`font-mono text-xs ${board.done ? 'text-up' : 'text-muted'}`}
              aria-live="polite"
            >
              {board.done ? 'ALL CLEAR · BONUS PAID' : `${done}/${total} done`}
            </span>
          </div>
        </>
      )}
    </Panel>
  )
}

function QuestCard({ item }: { item: QuestItem }) {
  const p = PERSONAS[item.persona]
  return (
    <motion.li layout initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}>
      <Link
        to={`/exercises/${item.slug}`}
        className={`flex h-full flex-col rounded border p-3 transition-colors ${
          item.completed ? 'border-up/40 bg-up/5' : 'border-line bg-panel-2 hover:border-amber/60'
        }`}
      >
        <div className="flex items-center justify-between font-mono text-[10px] tracking-wider text-muted">
          <span>{item.branch_title.toUpperCase()}</span>
          {item.completed ? (
            <span className="text-up">✓ DONE</span>
          ) : (
            <span>~{item.minutes} MIN</span>
          )}
        </div>
        <p className={`mt-2 text-sm ${item.completed ? 'text-muted line-through' : ''}`}>
          {item.title}
        </p>
        <p className="mt-auto pt-2 font-mono text-[11px] text-muted">
          <span style={{ color: p.color }}>{p.name}</span> · {item.node_title} ·{' '}
          {item.type.toUpperCase()}
        </p>
      </Link>
    </motion.li>
  )
}
