import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PyodideClient, PythonTimeoutError, type WorkerLike } from './client'
import { PYODIDE_VERSION, type FromWorker, type RunReport, type ToWorker } from './protocol'

class FakeWorker implements WorkerLike {
  onmessage: ((ev: MessageEvent<FromWorker>) => void) | null = null
  sent: ToWorker[] = []
  terminated = false
  postMessage(msg: ToWorker) {
    this.sent.push(msg)
  }
  terminate() {
    this.terminated = true
  }
  emit(msg: FromWorker) {
    this.onmessage?.({ data: msg } as MessageEvent<FromWorker>)
  }
  lastRunId(): number {
    const run = this.sent.filter((m) => m.type === 'run').at(-1)
    if (!run || run.type !== 'run') throw new Error('no run sent')
    return run.id
  }
}

const REPORT: RunReport = { setup_error: null, setup_stdout: '', tests: [] }
const flush = () => new Promise((r) => setTimeout(r, 0))

describe('PyodideClient', () => {
  let workers: FakeWorker[]
  let client: PyodideClient

  beforeEach(() => {
    workers = []
    client = new PyodideClient(() => {
      const w = new FakeWorker()
      workers.push(w)
      return w
    })
  })
  afterEach(() => vi.useRealTimers())

  it('boots once and reports ready', async () => {
    const statuses: string[] = []
    client.subscribe((s) => statuses.push(s.status))
    const a = client.init()
    const b = client.init()
    workers[0]!.emit({ type: 'ready' })
    await Promise.all([a, b])
    expect(workers).toHaveLength(1)
    expect(statuses).toEqual(['loading', 'ready'])
  })

  it('resolves a run with the worker report and reports phases', async () => {
    const phases: string[] = []
    const p = client.run('x = 1', 'def test_a(): pass', {
      packages: ['polars'],
      timeoutS: 5,
      onPhase: (ph) => phases.push(ph),
    })
    await flush()
    const w = workers[0]!
    w.emit({ type: 'ready' })
    await flush()
    const id = w.lastRunId()
    w.emit({ type: 'packages', id, names: ['polars'] })
    w.emit({ type: 'started', id })
    w.emit({ type: 'result', id, report: REPORT })
    await expect(p).resolves.toEqual(REPORT)
    expect(phases).toEqual(['queued', 'packages', 'running'])
  })

  it('times out only after code starts, kills the worker, and recovers', async () => {
    vi.useFakeTimers()
    const p = client.run('while True: pass', '', { timeoutS: 2 })
    const caught = p.catch((e: unknown) => e)
    await vi.advanceTimersByTimeAsync(0)
    const w = workers[0]!
    w.emit({ type: 'ready' })
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(10_000) // slow package load: no timeout yet
    expect(w.terminated).toBe(false)
    w.emit({ type: 'started', id: w.lastRunId() })
    await vi.advanceTimersByTimeAsync(2_001)
    expect(await caught).toBeInstanceOf(PythonTimeoutError)
    expect(w.terminated).toBe(true)
    expect(client.status.status).toBe('idle')

    const next = client.run('', '', { timeoutS: 2 })
    await vi.advanceTimersByTimeAsync(0)
    const w2 = workers[1]!
    w2.emit({ type: 'ready' })
    await vi.advanceTimersByTimeAsync(0)
    w2.emit({ type: 'started', id: w2.lastRunId() })
    w2.emit({ type: 'result', id: w2.lastRunId(), report: REPORT })
    await expect(next).resolves.toEqual(REPORT)
  })

  it('serializes runs and ignores stale messages', async () => {
    const a = client.run('a', '', { timeoutS: 5 })
    const b = client.run('b', '', { timeoutS: 5 })
    await flush()
    const w = workers[0]!
    w.emit({ type: 'ready' })
    await flush()
    expect(w.sent.filter((m) => m.type === 'run')).toHaveLength(1) // b waits for a
    const idA = w.lastRunId()
    w.emit({ type: 'result', id: idA + 99, report: REPORT }) // stale: ignored
    w.emit({ type: 'run-error', id: idA, message: 'boom' })
    await expect(a).rejects.toThrow('boom')
    await flush()
    const idB = w.lastRunId()
    expect(idB).not.toBe(idA)
    w.emit({ type: 'result', id: idB, report: REPORT })
    await expect(b).resolves.toEqual(REPORT)
  })

  it('surfaces init errors and allows a retry', async () => {
    const p = client.init()
    workers[0]!.emit({ type: 'init-error', message: 'CDN down' })
    await expect(p).rejects.toThrow('CDN down')
    expect(client.status).toEqual({ status: 'error', error: 'CDN down' })
    void client.init()
    expect(workers).toHaveLength(2)
  })
})

it('PYODIDE_VERSION matches the pinned npm package', () => {
  // vitest runs from frontend/ (jsdom's import.meta.url isn't a file: URL)
  const pkg = JSON.parse(readFileSync(resolve(process.cwd(), 'package.json'), 'utf8'))
  expect(pkg.dependencies.pyodide).toBe(PYODIDE_VERSION)
})
