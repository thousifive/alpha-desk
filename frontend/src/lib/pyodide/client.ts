import type { FromWorker, RunReport, ToWorker } from './protocol'

export type EngineStatus =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready' }
  | { status: 'error'; error: string }

export type RunPhase = 'queued' | 'packages' | 'running'

export class PythonTimeoutError extends Error {
  constructor(seconds: number) {
    super(`Timed out after ${seconds}s. Infinite loop? The Python engine was restarted.`)
  }
}

/** Minimal surface of `Worker`, so tests can pass a fake. */
export interface WorkerLike {
  postMessage(msg: ToWorker): void
  terminate(): void
  onmessage: ((ev: MessageEvent<FromWorker>) => void) | null
}

interface Pending {
  id: number
  timeoutS: number
  resolve: (r: RunReport) => void
  reject: (e: Error) => void
  onPhase?: (p: RunPhase) => void
  timer?: ReturnType<typeof setTimeout>
}

/**
 * Owns one Pyodide worker. Runs are serialized (Python is single-threaded anyway), the
 * timeout clock starts only once packages are loaded, and a timed-out worker is terminated
 * and replaced on the next use.
 */
export class PyodideClient {
  private worker: WorkerLike | null = null
  private ready: Promise<void> | null = null
  private pending: Pending | null = null
  private queue: Promise<unknown> = Promise.resolve()
  private nextId = 1
  private listeners = new Set<(s: EngineStatus) => void>()
  status: EngineStatus = { status: 'idle' }
  private readonly makeWorker: () => WorkerLike

  constructor(makeWorker: () => WorkerLike) {
    this.makeWorker = makeWorker
  }

  subscribe(fn: (s: EngineStatus) => void): () => void {
    this.listeners.add(fn)
    return () => this.listeners.delete(fn)
  }

  private setStatus(s: EngineStatus) {
    this.status = s
    for (const fn of this.listeners) fn(s)
  }

  /** Start (or reuse) the worker and wait until the interpreter is up. */
  init(): Promise<void> {
    if (this.ready) return this.ready
    this.setStatus({ status: 'loading' })
    const w = this.makeWorker()
    this.worker = w
    this.ready = new Promise<void>((resolve, reject) => {
      w.onmessage = (ev) => {
        const m = ev.data
        if (m.type === 'ready') {
          this.setStatus({ status: 'ready' })
          resolve()
        } else if (m.type === 'init-error') {
          this.reset()
          this.setStatus({ status: 'error', error: m.message })
          reject(new Error(m.message))
        } else {
          this.onRunMessage(m)
        }
      }
    })
    w.postMessage({ type: 'init' })
    return this.ready
  }

  run(
    code: string,
    tests: string,
    opts: { packages?: string[]; timeoutS: number; onPhase?: (p: RunPhase) => void },
  ): Promise<RunReport> {
    opts.onPhase?.('queued')
    const job = this.queue.then(() => this.runNow(code, tests, opts))
    this.queue = job.catch(() => undefined) // a failed run must not block the next one
    return job
  }

  private async runNow(
    code: string,
    tests: string,
    opts: { packages?: string[]; timeoutS: number; onPhase?: (p: RunPhase) => void },
  ): Promise<RunReport> {
    await this.init()
    const id = this.nextId++
    return new Promise<RunReport>((resolve, reject) => {
      this.pending = { id, timeoutS: opts.timeoutS, resolve, reject, onPhase: opts.onPhase }
      this.worker?.postMessage({ type: 'run', id, code, tests, packages: opts.packages ?? [] })
    })
  }

  private onRunMessage(m: FromWorker) {
    const p = this.pending
    if (!p || !('id' in m) || m.id !== p.id) return // stale message from a killed run
    switch (m.type) {
      case 'packages':
        p.onPhase?.('packages')
        break
      case 'started':
        p.onPhase?.('running')
        p.timer = setTimeout(() => this.timeout(p), p.timeoutS * 1000)
        break
      case 'result':
        this.finish(p)
        p.resolve(m.report)
        break
      case 'run-error':
        this.finish(p)
        p.reject(new Error(m.message))
        break
    }
  }

  private finish(p: Pending) {
    clearTimeout(p.timer)
    this.pending = null
  }

  private timeout(p: Pending) {
    this.finish(p)
    this.reset()
    this.setStatus({ status: 'idle' }) // next run boots a fresh interpreter
    p.reject(new PythonTimeoutError(p.timeoutS))
  }

  private reset() {
    this.worker?.terminate()
    this.worker = null
    this.ready = null
  }
}

let shared: PyodideClient | null = null

export function getPyodide(): PyodideClient {
  shared ??= new PyodideClient(
    () => new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' }) as WorkerLike,
  )
  return shared
}
