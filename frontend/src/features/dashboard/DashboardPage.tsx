import { Link } from 'react-router'

import { useBranch, useBranches, useProgress } from '../../api/hooks'
import type { BranchDetail, Progress } from '../../api/types'
import { LoadError } from '../../components/LoadError'
import { Locked } from '../../components/Locked'
import { Bar, Panel } from '../../components/ui'
import { exercisesLabel, nodesLabel, ratio } from '../../lib/counts'
import { PERSONAS } from '../../lib/personas'
import { TODOS } from '../../lib/todos'
import { QuestBoard } from './QuestBoard'
import { StreakCard } from './StreakCard'

export function DashboardPage() {
  const progress = useProgress()
  const branches = useBranches()
  const sql = useBranch('sql-olap')

  if (progress.isPending || branches.isPending) {
    return <p className="p-6 font-mono text-sm text-muted">Loading desk…</p>
  }
  if (progress.isError || branches.isError) {
    return <LoadError error={progress.error ?? branches.error} notFound="Nothing here." />
  }

  return (
    <main className="mx-auto grid w-full max-w-6xl gap-4 p-4 md:grid-cols-3 md:p-6">
      <LevelCard p={progress.data} />
      <StreakCard streak={progress.data.streak} />
      <BossCard p={progress.data} />

      <QuestBoard
        fallback={
          sql.data ? <UpNext branch={sql.data} /> : <p className="text-sm text-muted">Loading…</p>
        }
      />

      <Panel title="SKILL TREE">
        <ul className="space-y-3">
          {branches.data.map((b) => (
            <li key={b.id}>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                {b.playable ? (
                  <Link
                    to={`/branches/${b.id}`}
                    className="hover:text-amber pointer-coarse:inline-flex pointer-coarse:min-h-11 pointer-coarse:items-center"
                  >
                    {b.title}
                  </Link>
                ) : (
                  <span className="text-muted">{b.title}</span>
                )}
                <span className="font-mono text-[11px] text-muted">
                  {b.playable ? exercisesLabel(b) : `from ${b.playable_from}`}
                </span>
              </div>
              <div className="mt-1">
                <Bar value={ratio(b)} className={b.playable ? 'bg-amber' : 'bg-muted/40'} />
              </div>
              {b.playable && (
                <p className="mt-1 font-mono text-[10px] text-muted">{nodesLabel(b)}</p>
              )}
            </li>
          ))}
        </ul>
        {sql.data && <MiniMap branch={sql.data} />}
      </Panel>
    </main>
  )
}

function LevelCard({ p }: { p: Progress }) {
  const lv = p.level
  if (!lv) {
    return (
      <Panel title="LEVEL">
        <p className="font-mono text-3xl text-amber">
          {p.xp_total.toLocaleString()} <span className="text-base text-muted">XP</span>
        </p>
        <div className="mt-3">
          <Locked task={TODOS['#1']} />
        </div>
      </Panel>
    )
  }
  const span = lv.next_min_xp === null ? 1 : lv.next_min_xp - lv.min_xp
  const into = p.xp_total - lv.min_xp
  return (
    <Panel
      title="LEVEL"
      right={<span className="font-mono text-[11px] text-muted">L{lv.index + 1}</span>}
    >
      <p className="font-mono text-3xl font-semibold text-amber">{lv.title}</p>
      <div className="mt-3">
        <Bar value={lv.next_min_xp === null ? 1 : into / span} />
      </div>
      <p className="mt-2 font-mono text-xs text-muted">
        {p.xp_total.toLocaleString()} XP
        {lv.next_min_xp !== null && (
          <>
            {' '}
            · {(lv.next_min_xp - p.xp_total).toLocaleString()} to {lv.next_title}
          </>
        )}
      </p>
    </Panel>
  )
}

function BossCard({ p }: { p: Progress }) {
  const boss = p.next_boss
  return (
    <Panel title="NEXT BOSS" right={<span className="font-mono text-[10px] text-muted">M5</span>}>
      {boss ? (
        <>
          <p className="font-mono text-lg font-semibold text-violet">{boss.title}</p>
          <p className="mt-1 text-xs text-muted">{boss.description}</p>
          <p className="mt-3 font-mono text-[11px] text-muted">
            End of {boss.branch_title}
            {boss.stages > 1 && ` · boss ${boss.stage} of ${boss.stages}`}
          </p>
          <div className="mt-2">
            <Bar value={ratio(boss)} className="bg-violet" />
          </div>
          <p className="mt-1.5 font-mono text-[11px] text-muted">
            {exercisesLabel(boss)} · {nodesLabel(boss)}
          </p>
        </>
      ) : (
        <p className="text-sm text-muted">No boss queued.</p>
      )}
    </Panel>
  )
}

function UpNext({ branch }: { branch: BranchDetail }) {
  const next = branch.nodes
    .filter((n) => n.state === 'available')
    .flatMap((n) => n.exercises.filter((e) => !e.passed).map((e) => ({ ...e, node: n.title })))
    .slice(0, 4)
  if (next.length === 0) return <p className="text-sm text-up">Every open ticket is closed. 🎉</p>
  return (
    <ul className="divide-y divide-line">
      {next.map((e) => {
        const p = PERSONAS[e.persona]
        return (
          <li key={e.slug}>
            <Link
              to={`/exercises/${e.slug}`}
              className="flex items-center gap-3 py-2.5 hover:bg-panel-2"
            >
              <span
                className="grid size-7 shrink-0 place-items-center rounded-full font-mono text-xs font-semibold text-bg"
                style={{ background: p.color }}
              >
                {p.name[0]}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm">{e.title}</span>
                <span className="block font-mono text-[11px] text-muted">
                  {p.name} · {e.node} · {e.type.toUpperCase()}
                </span>
              </span>
              <span className="font-mono text-xs text-amber">OPEN →</span>
            </Link>
          </li>
        )
      })}
    </ul>
  )
}

const CELL: Record<string, string> = {
  mastered: 'bg-up',
  available: 'bg-amber',
  locked: 'bg-line',
  coming_soon: 'bg-panel-2',
}

/** Tiny node map for the SQL branch; the full D3 skill tree lands in M3. */
function MiniMap({ branch }: { branch: BranchDetail }) {
  return (
    <div className="mt-5">
      <p className="font-mono text-[10px] tracking-wider text-muted">
        {branch.title.toUpperCase()} NODES
      </p>
      <div className="mt-2 grid grid-cols-6 gap-1.5 pointer-coarse:grid-cols-[repeat(auto-fill,44px)]">
        {branch.nodes.map((n) => (
          <Link
            key={n.slug}
            to={`/branches/${branch.id}#${n.slug}`}
            title={`${n.title}: ${n.state}`}
            className={`aspect-square rounded-sm ${CELL[n.state]} hover:ring-1 hover:ring-ink`}
          />
        ))}
      </div>
    </div>
  )
}
