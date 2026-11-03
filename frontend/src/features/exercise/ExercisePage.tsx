import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import { useExercise, useSubmitAttempt } from '../../api/hooks'
import type { AttemptOut, Exercise, Level } from '../../api/types'
import { LevelUpModal } from '../../components/LevelUpModal'
import { XpPop } from '../../components/XpPop'
import { loadDraft, saveDraft } from '../../lib/drafts'
import { runQuery, type QueryResult } from '../../lib/duckdb/db'
import { useDuckDB } from '../../lib/duckdb/useDuckDB'
import { useHotkeys } from '../../lib/keyboard'
import { Markdown } from '../../lib/markdown'
import { QuizView } from './QuizView'
import { ResultGrid } from './ResultGrid'
import { SchemaPanel } from './SchemaPanel'
import { SqlEditor } from './SqlEditor'
import { SubmitFeedback } from './SubmitFeedback'
import { TicketHeader } from './TicketHeader'

export default function ExercisePage() {
  const { slug = '' } = useParams()
  const ex = useExercise(slug)

  if (ex.isPending) return <p className="p-6 font-mono text-sm text-muted">Loading ticket…</p>
  if (ex.isError) {
    return (
      <p className="p-6 font-mono text-sm text-down">
        {ex.error instanceof ApiError && ex.error.status === 404
          ? 'No such ticket.'
          : 'Failed to load ticket.'}
      </p>
    )
  }
  // Keyed by slug: moving to the next ticket remounts with fresh editor/result/feedback state.
  return <Desk key={ex.data.slug} ex={ex.data} />
}

function Desk({ ex }: { ex: Exercise }) {
  const playable = ex.node_state === 'available' || ex.node_state === 'mastered'
  return (
    <main className="grid min-h-0 flex-1 lg:h-[calc(100dvh-2.75rem)] lg:grid-cols-[minmax(320px,420px)_1fr]">
      <aside className="overflow-y-auto border-line p-5 lg:border-r">
        <TicketHeader ex={ex} />
        <div className="mt-4 text-sm text-ink/90">
          <Markdown source={ex.prompt_md} />
        </div>
        {ex.passed && (
          <p className="mt-3 font-mono text-xs text-up">✓ You've closed this ticket before.</p>
        )}
        {ex.type === 'sql' && <SchemaSection />}
      </aside>
      {!playable ? (
        <LockedNotice ex={ex} />
      ) : ex.type === 'sql' ? (
        <SqlWorkbench ex={ex} />
      ) : ex.type === 'quiz' ? (
        <QuizWorkbench ex={ex} />
      ) : (
        <LockedNotice ex={ex} />
      )}
    </main>
  )
}

function SchemaSection() {
  const db = useDuckDB()
  if (db.status === 'ready') return <SchemaPanel schema={db.schema} />
  if (db.status === 'error')
    return <p className="mt-6 font-mono text-xs text-down">DuckDB failed: {db.error}</p>
  return (
    <p className="mt-6 font-mono text-xs text-muted">
      Loading market data
      {db.progress ? ` (${db.progress.loaded}/${db.progress.total} tables)` : '…'}
    </p>
  )
}

function LockedNotice({ ex }: { ex: Exercise }) {
  return (
    <section className="grid place-items-center p-8 text-center">
      <div>
        <p className="font-mono text-sm text-muted">
          {ex.node_state === 'locked'
            ? 'This node is locked. Master its prerequisites first.'
            : 'This ticket type unlocks in a later milestone.'}
        </p>
        <Link
          to={`/branches/${ex.branch_id}`}
          className="mt-3 inline-block font-mono text-xs text-amber"
        >
          ← BACK TO BRANCH
        </Link>
      </div>
    </section>
  )
}

/** Shared submit plumbing: XP pop, level-up detection, error text for 501 TODO(me)s. */
function useSubmission(ex: Exercise) {
  const submit = useSubmitAttempt(ex.slug)
  const [out, setOut] = useState<AttemptOut | null>(null)
  const [levelUp, setLevelUp] = useState<Level | null>(null)
  const [popId, setPopId] = useState(0)
  const [startedAt] = useState(() => performance.now())

  const send = useCallback(
    async (body: { code: string; result?: QueryResult; choice?: number }) => {
      const res = await submit.mutateAsync({
        code: body.code,
        result: body.result && { columns: body.result.columns, rows: body.result.rows },
        choice: body.choice,
        duration_ms: Math.round(performance.now() - startedAt),
      })
      setOut(res)
      if (res.passed && res.xp_awarded + res.node_bonus_xp > 0) setPopId((n) => n + 1)
      if (res.level_before && res.level_after && res.level_after.index > res.level_before.index) {
        setLevelUp(res.level_after)
      }
    },
    [submit, startedAt],
  )

  const error =
    submit.error instanceof ApiError
      ? submit.error.status === 501
        ? `${submit.error.message}. Finish it in the backend to enable submitting.`
        : submit.error.message
      : submit.error
        ? String(submit.error)
        : null

  const pop = out && out.passed ? out.xp_awarded + out.node_bonus_xp : 0
  const overlay = (
    <>
      <XpPop id={popId} amount={pop} />
      <LevelUpModal level={levelUp} onClose={() => setLevelUp(null)} />
    </>
  )
  return { send, out, error, pending: submit.isPending, overlay }
}

function SqlWorkbench({ ex }: { ex: Exercise }) {
  const db = useDuckDB()
  const [code, setCode] = useState(
    () => loadDraft(ex.slug) ?? (ex.starter_code || '-- Write your query. ⌘↵ runs, ⌘⇧↵ submits.\n'),
  )
  const [result, setResult] = useState<QueryResult | null>(null)
  const [queryError, setQueryError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const { send, out, error, pending, overlay } = useSubmission(ex)
  const ready = db.status === 'ready'

  useEffect(() => {
    const t = setTimeout(() => saveDraft(ex.slug, code), 400) // debounce localStorage writes
    return () => clearTimeout(t)
  }, [ex.slug, code])

  const run = useCallback(async (): Promise<QueryResult | null> => {
    if (!ready || running) return null
    setRunning(true)
    setQueryError(null)
    try {
      const r = await runQuery(code)
      setResult(r)
      return r
    } catch (e) {
      // DuckDB errors are user-facing gold ("Binder Error: column x not found"): show them verbatim.
      setQueryError(e instanceof Error ? e.message : String(e))
      setResult(null)
      return null
    } finally {
      setRunning(false)
    }
  }, [code, ready, running])

  // Submit always re-runs the current editor contents, so what's graded is what you see.
  const submitNow = useCallback(async () => {
    if (pending) return
    const r = await run()
    if (r) await send({ code, result: r }).catch(() => undefined)
  }, [code, pending, run, send])

  useHotkeys({ onRun: () => void run(), onSubmit: () => void submitNow() })

  return (
    <section className="grid min-h-[70dvh] grid-rows-[minmax(200px,1fr)_auto_minmax(160px,1fr)] lg:min-h-0">
      <div className="min-h-0 border-b border-line">
        <SqlEditor
          value={code}
          onChange={setCode}
          onRun={() => void run()}
          onSubmit={() => void submitNow()}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-panel px-3 py-2">
        <button
          onClick={() => void run()}
          disabled={!ready || running}
          className="rounded border border-line px-3 py-1 font-mono text-xs hover:border-muted disabled:opacity-40"
        >
          {running ? 'RUNNING…' : 'RUN'} <kbd className="ml-1 text-muted">⌘↵</kbd>
        </button>
        <div className="relative">
          <button
            onClick={() => void submitNow()}
            disabled={!ready || pending}
            className="rounded bg-amber px-3 py-1 font-mono text-xs font-semibold text-bg disabled:opacity-40"
          >
            {pending ? 'GRADING…' : 'SUBMIT'} <kbd className="ml-1 opacity-60">⌘⇧↵</kbd>
          </button>
          {overlay}
        </div>
        {!ready && <span className="font-mono text-xs text-muted">warming up DuckDB…</span>}
        {error && <span className="font-mono text-xs text-down">{error}</span>}
      </div>
      <div className="flex min-h-0 flex-col">
        {out && (
          <div className="border-b border-line p-3">
            <SubmitFeedback out={out} nextSlug={ex.next_slug} branchId={ex.branch_id} />
          </div>
        )}
        <div className="min-h-0 flex-1">
          {queryError ? (
            <pre className="whitespace-pre-wrap p-3 font-mono text-xs text-down">{queryError}</pre>
          ) : result ? (
            <ResultGrid result={result} />
          ) : (
            <p className="p-3 font-mono text-xs text-muted">Run a query to see results.</p>
          )}
        </div>
      </div>
    </section>
  )
}

function QuizWorkbench({ ex }: { ex: Exercise }) {
  const [choice, setChoice] = useState<number | null>(null)
  const { send, out, error, pending, overlay } = useSubmission(ex)
  const answered = out !== null

  const submitNow = useCallback(() => {
    if (choice === null || pending || out?.passed) return
    void send({ code: '', choice }).catch(() => undefined)
  }, [choice, pending, out, send])

  useHotkeys({ onSubmit: submitNow })

  return (
    <section className="mx-auto w-full max-w-2xl p-5">
      <QuizView
        choices={ex.choices}
        selected={choice}
        onSelect={setChoice}
        locked={pending || !!out?.passed}
      />
      <div className="mt-4 flex items-center gap-3">
        <div className="relative">
          <button
            onClick={submitNow}
            disabled={choice === null || pending || !!out?.passed}
            className="rounded bg-amber px-4 py-2 font-mono text-xs font-semibold text-bg disabled:opacity-40"
          >
            {pending ? 'CHECKING…' : answered && !out.passed ? 'TRY AGAIN' : 'SUBMIT'}
          </button>
          {overlay}
        </div>
        <span className="font-mono text-xs text-muted">
          1–{ex.choices.length} to pick · ⌘⇧↵ to submit
        </span>
      </div>
      {error && <p className="mt-3 font-mono text-xs text-down">{error}</p>}
      {out && (
        <div className="mt-4">
          <SubmitFeedback out={out} nextSlug={ex.next_slug} branchId={ex.branch_id} />
        </div>
      )}
    </section>
  )
}
