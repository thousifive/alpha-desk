import { Link, useParams } from 'react-router'

import { useBranch } from '../../api/hooks'
import type { SkillNode } from '../../api/types'
import { Bar, StateBadge } from '../../components/ui'
import { PERSONAS } from '../../lib/personas'
import { Difficulty } from '../exercise/TicketHeader'

export function BranchPage() {
  const { branchId = '' } = useParams()
  const branch = useBranch(branchId)

  if (branch.isPending) return <p className="p-6 font-mono text-sm text-muted">Loading branch…</p>
  if (branch.isError) return <p className="p-6 font-mono text-sm text-down">Unknown branch.</p>
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
            <Bar value={b.n_exercises ? b.n_passed / b.n_exercises : 0} />
          </div>
          <span className="font-mono text-xs text-muted">
            {b.n_passed}/{b.n_exercises} tickets · {b.n_mastered}/{b.n_nodes} nodes
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
        {b.boss && (
          <li className="relative">
            <span
              className="absolute -left-[31px] top-3 size-3 rounded-full border-2 border-down bg-bg"
              aria-hidden
            />
            <div className="rounded-lg border border-down/40 bg-down/5 p-4">
              <p className="font-mono text-[11px] tracking-wider text-down">BOSS · M5</p>
              <p className="mt-1 font-mono text-lg font-semibold">{b.boss.title}</p>
              <p className="mt-1 text-sm text-muted">{b.boss.description}</p>
            </div>
          </li>
        )}
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
  const passed = node.exercises.filter((e) => e.passed).length
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
            <p>
              {passed}/{node.exercises.length}
            </p>
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
