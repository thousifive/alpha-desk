// Messages between the main thread and the Pyodide worker. Shapes of `RunReport` mirror the
// dict returned by backend/app/pyrunner/harness.py:run_tests.

export const PYODIDE_VERSION = '314.0.7' // keep equal to package.json (checked in a test)
export const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`

export interface TestReport {
  name: string
  passed: boolean
  duration_ms: number
  stdout: string
  error: string | null
}

export interface RunReport {
  setup_error: string | null
  setup_stdout: string
  tests: TestReport[]
}

export type ToWorker =
  { type: 'init' } | { type: 'run'; id: number; code: string; tests: string; packages: string[] }

export type FromWorker =
  | { type: 'ready' }
  | { type: 'init-error'; message: string }
  | { type: 'packages'; id: number; names: string[] }
  /** Packages are loaded and user code is about to execute: the timeout starts now. */
  | { type: 'started'; id: number }
  | { type: 'result'; id: number; report: RunReport }
  | { type: 'run-error'; id: number; message: string }
