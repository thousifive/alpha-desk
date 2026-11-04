import { useCallback, useEffect, useRef, useState } from 'react'

import { getHiddenTests } from '../../api/hooks'
import type { Exercise } from '../../api/types'
import { Locked } from '../../components/Locked'
import { loadDraft, saveDraft } from '../../lib/drafts'
import { useHotkeys } from '../../lib/keyboard'
import { getPyodide, type RunPhase } from '../../lib/pyodide/client'
import type { RunReport } from '../../lib/pyodide/protocol'
import { usePyodide } from '../../lib/pyodide/usePyodide'
import { CodeEditor } from './CodeEditor'
import { SubmitFeedback } from './SubmitFeedback'
import { TestResults } from './TestResults'
import { useSubmission } from './useSubmission'

type Tab = 'results' | 'tests'
type Busy = null | { what: 'run' | 'submit'; phase: RunPhase | 'fetching' }

const PHASE_LABEL: Record<NonNullable<Busy>['phase'], string> = {
  fetching: 'fetching tests…',
  queued: 'starting Python…',
  packages: 'loading packages…',
  running: 'running…',
}

export default function PythonWorkbench({ ex }: { ex: Exercise }) {
  const engine = usePyodide()
  const [code, setCode] = useState(() => loadDraft(ex.slug) ?? ex.starter_code)
  const [report, setReport] = useState<{ kind: 'visible' | 'hidden'; data: RunReport } | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [busy, setBusy] = useState<Busy>(null)
  const [tab, setTab] = useState<Tab>('results')
  const hidden = useRef<string | null>(null) // fetched once per mount, at first Submit
  const { send, out, error, locked, pending, overlay } = useSubmission(ex)

  useEffect(() => {
    const t = setTimeout(() => saveDraft(ex.slug, code), 400)
    return () => clearTimeout(t)
  }, [ex.slug, code])

  const exec = useCallback(
    async (tests: string, what: 'run' | 'submit'): Promise<RunReport | null> => {
      setRunError(null)
      setTab('results')
      try {
        return await getPyodide().run(code, tests, {
          packages: ex.packages,
          timeoutS: ex.timeout_s,
          onPhase: (phase) => setBusy({ what, phase }),
        })
      } catch (e) {
        setRunError(e instanceof Error ? e.message : String(e))
        return null
      }
    },
    [code, ex.packages, ex.timeout_s],
  )

  const run = useCallback(async () => {
    if (busy) return
    if (!ex.visible_tests.trim()) {
      setRunError('This ticket has no visible tests. Submit runs the hidden ones.')
      return
    }
    const r = await exec(ex.visible_tests, 'run')
    setBusy(null)
    if (r) setReport({ kind: 'visible', data: r })
  }, [busy, ex.visible_tests, exec])

  const submitNow = useCallback(async () => {
    if (busy || pending) return
    setBusy({ what: 'submit', phase: 'fetching' })
    try {
      hidden.current ??= await getHiddenTests(ex.slug)
    } catch (e) {
      setBusy(null)
      setRunError(e instanceof Error ? e.message : String(e))
      return
    }
    const r = await exec(hidden.current, 'submit')
    setBusy(null)
    if (!r) return
    setReport({ kind: 'hidden', data: r })
    // Code that doesn't even import isn't an attempt; fix it first (same as a SQL error).
    if (r.setup_error) return
    await send({ code, tests: r.tests.map((t) => ({ name: t.name, passed: t.passed })) }).catch(
      () => undefined,
    )
  }, [busy, pending, ex.slug, exec, send, code])

  useHotkeys({ onRun: () => void run(), onSubmit: () => void submitNow() })

  const engineNote =
    engine.status === 'loading'
      ? 'warming up Python (first load ~10 MB)…'
      : engine.status === 'error'
        ? `Python failed to load: ${engine.error}`
        : null

  return (
    <section className="grid min-h-[70dvh] grid-cols-[minmax(0,1fr)] grid-rows-[minmax(220px,1fr)_auto_minmax(180px,1fr)] lg:min-h-0">
      <div className="min-h-0 border-b border-line">
        <CodeEditor
          language="python"
          value={code}
          onChange={setCode}
          onRun={() => void run()}
          onSubmit={() => void submitNow()}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-panel px-3 py-2">
        <button
          onClick={() => void run()}
          disabled={!!busy}
          className="min-h-11 rounded border border-line px-4 font-mono text-xs hover:border-muted disabled:opacity-40 pointer-fine:min-h-0 pointer-fine:px-3 pointer-fine:py-1"
        >
          {busy?.what === 'run' ? 'RUNNING…' : 'RUN TESTS'}{' '}
          <kbd className="ml-1 text-muted max-sm:hidden">⌘↵</kbd>
        </button>
        <div className="relative">
          <button
            onClick={() => void submitNow()}
            disabled={!!busy || pending}
            className="min-h-11 rounded bg-amber px-4 font-mono text-xs font-semibold text-bg disabled:opacity-40 pointer-fine:min-h-0 pointer-fine:px-3 pointer-fine:py-1"
          >
            {pending || busy?.what === 'submit' ? 'GRADING…' : 'SUBMIT'}{' '}
            <kbd className="ml-1 opacity-60 max-sm:hidden">⌘⇧↵</kbd>
          </button>
          {overlay}
        </div>
        <button
          onClick={() => {
            if (window.confirm('Reset the editor to the starter code?')) setCode(ex.starter_code)
          }}
          className="min-h-11 px-2 font-mono text-[11px] text-muted hover:text-ink pointer-fine:min-h-0"
        >
          RESET
        </button>
        {busy && <span className="font-mono text-xs text-muted">{PHASE_LABEL[busy.phase]}</span>}
        {!busy && engineNote && (
          <span
            className={`font-mono text-xs ${engine.status === 'error' ? 'text-down' : 'text-muted'}`}
          >
            {engineNote}
          </span>
        )}
        {error && <span className="font-mono text-xs text-down">{error}</span>}
        {locked && <Locked task={locked} compact />}
      </div>
      <div className="flex min-h-0 flex-col">
        {out && (
          <div className="border-b border-line p-3">
            <SubmitFeedback out={out} nextSlug={ex.next_slug} branchId={ex.branch_id} />
          </div>
        )}
        <div className="flex gap-1 border-b border-line px-2 font-mono text-[11px]" role="tablist">
          {(['results', 'tests'] as const).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`min-h-11 px-3 pointer-fine:min-h-0 pointer-fine:px-2 pointer-fine:py-1.5 ${tab === t ? 'border-b border-amber text-amber' : 'text-muted hover:text-ink'}`}
            >
              {t === 'results' ? 'RESULTS' : 'VISIBLE TESTS'}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {tab === 'tests' ? (
            <pre className="whitespace-pre-wrap p-3 font-mono text-xs text-ink/90">
              {ex.visible_tests || '# No visible tests for this ticket.'}
            </pre>
          ) : runError ? (
            <pre className="whitespace-pre-wrap p-3 font-mono text-xs text-down">{runError}</pre>
          ) : report ? (
            <TestResults report={report.data} kind={report.kind} />
          ) : (
            <p className="p-3 font-mono text-xs text-muted">
              ⌘↵ runs the visible tests. ⌘⇧↵ submits against the hidden ones.
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
