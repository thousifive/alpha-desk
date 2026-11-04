import { beforeEach, describe, expect, it } from 'vitest'

import { KernelClient, type KernelWorkerLike } from '../kernel/client'
import type { FromKernel, ToKernel } from '../kernel/protocol'
import { LocalEngine, NoBundleError } from './engine'
import { mergeEvents, setCache } from './store'
import { ev, freshDB } from './testing'

/** Records what the engine sends and answers like app/kernel.py would. */
class FakeKernel implements KernelWorkerLike {
  onmessage: ((ev: MessageEvent<FromKernel>) => void) | null = null
  calls: ToKernel[] = []
  postMessage(msg: ToKernel) {
    this.calls.push(msg)
    const result = msg.op === 'snapshot' ? '{"event_count":0}' : 'null'
    queueMicrotask(() =>
      this.onmessage?.({ data: { id: msg.id, ok: true, result } } as MessageEvent<FromKernel>),
    )
  }
  terminate() {}
  ops() {
    return this.calls.map((c) => c.op)
  }
  fed(): { id: string; payload: Record<string, unknown> }[] {
    return this.calls.filter((c) => c.op === 'add_events').flatMap((c) => JSON.parse(c.arg))
  }
}

describe('LocalEngine', () => {
  let workers: FakeKernel[]
  let engine: LocalEngine

  beforeEach(async () => {
    freshDB()
    workers = []
    engine = new LocalEngine(
      new KernelClient(() => {
        const w = new FakeKernel()
        workers.push(w)
        return w
      }),
    )
    await setCache('bundle', { version: 'v1', milestone: 'M2', content: {} })
  })

  it('needs a downloaded bundle', async () => {
    freshDB()
    await expect(engine.snapshot('2026-11-04')).rejects.toBeInstanceOf(NoBundleError)
  })

  it('loads the bundle once and feeds each event once, without player code', async () => {
    await mergeEvents([ev(1), ev(2)])
    await engine.snapshot('2026-11-04')
    await mergeEvents([ev(3)])
    await engine.snapshot('2026-11-04')
    await engine.snapshot('2026-11-04')
    const w = workers[0]!
    expect(w.ops().filter((o) => o === 'load_bundle')).toHaveLength(1)
    expect(w.fed().map((e) => e.id)).toEqual([ev(1).id, ev(2).id, ev(3).id])
    expect(w.fed().every((e) => !('code' in e.payload))).toBe(true)
  })

  it('reloads when the bundle version changes', async () => {
    await engine.snapshot('2026-11-04')
    await setCache('bundle', { version: 'v2', milestone: 'M2', content: {} })
    await engine.snapshot('2026-11-04')
    expect(workers[0]!.ops().filter((o) => o === 'load_bundle')).toHaveLength(2)
  })

  it('re-feeds everything to a fresh worker after dispose', async () => {
    await mergeEvents([ev(1)])
    await engine.snapshot('2026-11-04')
    engine.dispose()
    await engine.snapshot('2026-11-04')
    expect(workers).toHaveLength(2)
    expect(workers[1]!.ops().slice(0, 3)).toEqual(['reset_events', 'load_bundle', 'add_events'])
    expect(workers[1]!.fed().map((e) => e.id)).toEqual([ev(1).id])
  })

  it('serializes concurrent calls so no event is fed twice', async () => {
    await mergeEvents([ev(1), ev(2)])
    await Promise.all([engine.snapshot('a'), engine.snapshot('b'), engine.exercise('x')])
    expect(workers[0]!.fed()).toHaveLength(2)
  })
})
