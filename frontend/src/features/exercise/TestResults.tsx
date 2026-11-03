import type { RunReport } from '../../lib/pyodide/protocol'

interface Props {
  report: RunReport
  /** Hidden-test runs label themselves so it's clear these decide the grade. */
  kind: 'visible' | 'hidden'
}

export function TestResults({ report, kind }: Props) {
  const passed = report.tests.filter((t) => t.passed).length
  const total = report.tests.length
  return (
    <div className="space-y-2 p-3 font-mono text-xs">
      <p className="text-muted">
        {kind === 'hidden' ? 'HIDDEN TESTS' : 'VISIBLE TESTS'}
        {!report.setup_error && (
          <span className={passed === total ? 'ml-2 text-up' : 'ml-2 text-down'}>
            {passed}/{total} passed
          </span>
        )}
      </p>
      {report.setup_stdout && <Stdout text={report.setup_stdout} label="module output" />}
      {report.setup_error && (
        <pre className="whitespace-pre-wrap rounded border border-down/40 bg-down/10 p-2 text-down">
          {report.setup_error}
        </pre>
      )}
      {total === 0 && !report.setup_error && (
        <p className="text-muted">No tests ran. Define functions named test_* in the tests.</p>
      )}
      <ul className="space-y-1.5">
        {report.tests.map((t) => (
          <li key={t.name} className="rounded border border-line bg-panel">
            <div className="flex items-center gap-2 px-2 py-1.5">
              <span className={t.passed ? 'text-up' : 'text-down'} aria-hidden>
                {t.passed ? '✓' : '✗'}
              </span>
              <span className="min-w-0 flex-1 truncate">{t.name}</span>
              <span className="sr-only">{t.passed ? 'passed' : 'failed'}</span>
              <span className="text-[10px] text-muted">{t.duration_ms.toFixed(1)} ms</span>
            </div>
            {t.error && (
              <pre className="whitespace-pre-wrap border-t border-line px-2 py-1.5 text-down">
                {t.error}
              </pre>
            )}
            {t.stdout && <Stdout text={t.stdout} />}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Stdout({ text, label = 'stdout' }: { text: string; label?: string }) {
  return (
    <div className="border-t border-line px-2 py-1.5">
      <p className="text-[10px] tracking-wider text-muted">{label.toUpperCase()}</p>
      <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap text-ink/90">{text}</pre>
    </div>
  )
}
