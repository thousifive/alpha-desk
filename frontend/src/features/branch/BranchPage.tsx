import { Link, useParams } from 'react-router'

import { useBranch } from '../../api/hooks'
import type { SkillNode } from '../../api/types'
import { LoadError } from '../../components/LoadError'
import { Bar, StateBadge } from '../../components/ui'
import { exercisesLabel, nodesLabel, ratio } from '../../lib/counts'
import { PERSONAS } from '../../lib/personas'
import { Difficulty } from '../exercise/TicketHeader'

export function BranchPage() {
  const { branchId = '' } = useParams()
  const branch = useBranch(branchId)

  if (branch.isPending) return <p className="p-6 font-mono text-sm text-muted">Loading branch…</p>
  if (branch.isError) return <LoadError error={branch.error} notFound="Unknown branch." />
  const b = branch.data
  const titles = Object.fromEntries(b.nodes.map((n) => [n.slug, n.title]))

  return (
    <main className="mx-auto w-full max-w-4xl p-4 md:p-6">
      <header>
        <p className="font-mono text-[11px] tracking-wider text-muted">BRANCH</p>
        <h1 className="mt-1 text-2xl font-semibold">{b.title}</h1>
        <p className="mt-1 text-sm text-muted">{b.description}</p>
        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1">
            <Bar value={ratio(b)} />
          </div>
          <span className="font-mono text-xs text-muted">
            {exercisesLabel(b)} · {nodesLabel(b)}
          </span>
        </div>
        {!b.playable && (
          <p className="mt-3 font-mono text-xs text-muted">Playable from {b.playable_from}.</p>
        )}
      </header>

      <ol className="relative mt-8 space-y-4 border-l border-line pl-6">
        {b.nodes.map((n) => (
          <NodeCard key={n.slug} node={n} titles={titles} />
        ))}
        {b.bosses.map((boss) => (
          <li key={boss.title} className="relative">
            <span
              className="absolute -left-[31px] top-3 size-3 rounded-full border-2 border-violet bg-bg"
              aria-hidden
            />
            <div className="rounded-lg border border-violet/40 bg-violet/5 p-4">
              <p className="font-mono text-[11px] tracking-wider text-violet">
                BOSS{boss.stages > 1 && ` ${boss.stage}/${boss.stages}`} · M5
              </p>
              <p className="mt-1 font-mono text-lg font-semibold">{boss.title}</p>
              <p className="mt-1 text-sm text-muted">{boss.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </main>
  )
}

function NodeCard({ node, titles }: { node: SkillNode; titles: Record<string, string> }) {
  const open = node.state === 'available' || node.state === 'mastered'
  const dot = {
    mastered: 'bg-up border-up',
    available: 'bg-amber border-amber',
    locked: 'bg-bg border-line',
    coming_soon: 'bg-bg border-line',
  }[node.state]
  return (
    <li id={node.slug} className="relative scroll-mt-16">
      <span
        className={`absolute -left-[31px] top-4 size-3 rounded-full border-2 ${dot}`}
        aria-hidden
      />
      <div className={`rounded-lg border border-line bg-panel ${open ? '' : 'opacity-60'}`}>
        <div className="flex items-start gap-3 p-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-muted">
                {String(node.order).padStart(2, '0')}
              </span>
              <h2 className="font-semibold">{node.title}</h2>
              <StateBadge state={node.state} />
            </div>
            <p className="mt-1 text-sm text-muted">{node.description}</p>
            {node.state === 'locked' && node.prerequisites.length > 0 && (
              <p className="mt-2 font-mono text-[11px] text-muted">
                Requires: {node.prerequisites.map((p) => titles[p] ?? p).join(', ')}
              </p>
            )}
          </div>
          <div className="text-right font-mono text-[11px] text-muted">
            <p>{exercisesLabel(node)}</p>
            <p className="text-amber">+{node.xp_reward} bonus</p>
          </div>
        </div>
        {open && (
          <ul className="divide-y divide-line border-t border-line">
            {node.exercises.map((e) => {
              const p = PERSONAS[e.persona]
              return (
                <li key={e.slug}>
                  <Link
                    to={`/exercises/${e.slug}`}
                    className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-panel-2"
                  >
                    <span className={`font-mono text-xs ${e.passed ? 'text-up' : 'text-muted'}`}>
                      {e.passed ? '✓' : '○'}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{e.title}</span>
                    <span
                      className="hidden font-mono text-[11px] sm:inline"
                      style={{ color: p.color }}
                    >
                      {p.name}
                    </span>
                    <span className="font-mono text-[10px] text-muted">{e.type.toUpperCase()}</span>
                    <span className="w-8">
                      <Difficulty level={e.difficulty} />
                    </span>
                  </Link>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </li>
  )
}
