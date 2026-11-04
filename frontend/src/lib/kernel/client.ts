import type { FromKernel, KernelOp, ToKernel } from './protocol'

export interface KernelWorkerLike {
  postMessage(msg: ToKernel): void
  terminate(): void
  onmessage: ((ev: MessageEvent<FromKernel>) => void) | null
}

export class KernelError extends Error {}

/**
 * Request/response over one rules worker. Calls are matched to replies by id, so callers can
 * fire several at once; Python itself runs them one at a time in arrival order.
 */
export class KernelClient {
  private worker: KernelWorkerLike | null = null
  private nextId = 1
  private waiting = new Map<number, { resolve: (s: string) => void; reject: (e: Error) => void }>()
  private bootListeners = new Set<() => void>()
  booted = false
  /** Bumped whenever a fresh worker starts, so callers know its in-memory state is empty. */
  generation = 0
  private readonly makeWorker: () => KernelWorkerLike

  constructor(makeWorker: () => KernelWorkerLike) {
    this.makeWorker = makeWorker
  }

  private ensure(): KernelWorkerLike {
    if (this.worker) return this.worker
    const w = this.makeWorker()
    this.generation += 1
    this.booted = false
    w.onmessage = (ev) => {
      const msg = ev.data
      if (msg.id === 0) {
        this.booted = true
        for (const fn of this.bootListeners) fn()
        return
      }
      const p = this.waiting.get(msg.id)
      if (!p) return
      this.waiting.delete(msg.id)
      if (msg.ok) p.resolve(msg.result)
      else p.reject(new KernelError(msg.error))
    }
    this.worker = w
    return w
  }

  onBoot(fn: () => void): () => void {
    this.bootListeners.add(fn)
    return () => this.bootListeners.delete(fn)
  }

  call(op: KernelOp, arg = ''): Promise<string> {
    const w = this.ensure()
    const id = this.nextId++
    return new Promise((resolve, reject) => {
      this.waiting.set(id, { resolve, reject })
      w.postMessage({ id, op, arg })
    })
  }

  async json<T>(op: KernelOp, arg = ''): Promise<T> {
    return JSON.parse(await this.call(op, arg)) as T
  }

  /** Kill the worker (e.g. to free memory on iOS). The next call boots a fresh one. */
  dispose() {
    this.worker?.terminate()
    this.worker = null
    for (const p of this.waiting.values()) p.reject(new KernelError('rules worker stopped'))
    this.waiting.clear()
  }
}
