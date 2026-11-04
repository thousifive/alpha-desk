import type {
  AttemptIn,
  AttemptOut,
  BranchDetail,
  BranchSummary,
  Exercise,
  Progress,
  QuestBoard,
} from '../../api/types'
import { KernelClient, type KernelWorkerLike } from '../kernel/client'
import type { StoredEvent } from './db'
import type { LogEvent } from './events'
import { eventsAfter, getCache } from './store'

export interface Bundle {
  version: string
  milestone: string
  content: unknown // validated by ContentBundle in the worker
}

export interface Snapshot {
  progress: Progress
  branches: BranchSummary[]
  details: Record<string, BranchDetail>
  event_count: number
}

export interface QuestPlan {
  day: string
  items: [number, string][] // [position, exercise slug]
}

export interface SubmitRequest {
  slug: string
  attempt: AttemptIn
  expected?: { columns: string[]; rows: unknown[][] }
  device_id: string
  now: string
  today: string
  quest_plan?: [number, string][] | null
}

export type SubmitResponse =
  | { status: 'ok'; out: AttemptOut; events: LogEvent[] }
  | { status: 'locked'; message: string }
  | { status: 'rejected'; message: string }

/** The device has never downloaded the content bundle (first run with the server off). */
export class NoBundleError extends Error {
  constructor() {
    super('Connect to the server once to download the desk.')
  }
}

const KERNEL_EVENT_BATCH = 500

/** Strip the player's code from attempts: the rules don't need it and it's the bulk of the log. */
function forKernel(e: StoredEvent): LogEvent {
  const { lseq: _l, synced: _s, ...rest } = e
  if (rest.type !== 'attempt' || !('code' in rest.payload)) return rest
  const { code: _c, ...payload } = rest.payload
  return { ...rest, payload }
}

/**
 * Keeps the rules worker in step with IndexedDB: loads the content bundle when its version
 * changes and feeds it only the events it hasn't seen (by lseq). If the worker restarts, it
 * starts empty, so everything is fed again.
 */
export class LocalEngine {
  private readonly kernel: KernelClient
  private gen = -1
  private bundleVersion: string | null = null
  private fed = 0
  private chain: Promise<unknown> = Promise.resolve()

  constructor(kernel: KernelClient) {
    this.kernel = kernel
  }

  // A tiny mutex: every call runs `prepare` then its op, one after another, so two
  // concurrent queries can't feed the same events twice.
  private run<T>(fn: () => Promise<T>): Promise<T> {
    const next = this.chain.then(async () => {
      await this.prepare()
      return fn()
    })
    this.chain = next.catch(() => undefined)
    return next
  }

  private async prepare(): Promise<void> {
    const bundle = await getCache<Bundle>('bundle')
    if (!bundle) throw new NoBundleError()
    if (this.kernel.generation !== this.gen) {
      await this.kernel.call('reset_events') // also boots the worker on first use
      this.gen = this.kernel.generation
      this.bundleVersion = null
      this.fed = 0
    }
    if (bundle.version !== this.bundleVersion) {
      await this.kernel.call('load_bundle', JSON.stringify(bundle))
      this.bundleVersion = bundle.version
    }
    for (;;) {
      const fresh = await eventsAfter(this.fed)
      if (fresh.length === 0) break
      for (let i = 0; i < fresh.length; i += KERNEL_EVENT_BATCH) {
        const batch = fresh.slice(i, i + KERNEL_EVENT_BATCH)
        await this.kernel.call('add_events', JSON.stringify(batch.map(forKernel)))
        this.fed = batch[batch.length - 1]!.lseq ?? this.fed
      }
    }
  }

  snapshot(today: string): Promise<Snapshot> {
    return this.run(() => this.kernel.json<Snapshot>('snapshot', today))
  }

  exercise(slug: string): Promise<Exercise | null> {
    return this.run(() => this.kernel.json<Exercise | null>('exercise', slug))
  }

  quests(plan: QuestPlan): Promise<QuestBoard> {
    return this.run(() => this.kernel.json<QuestBoard>('quests', JSON.stringify(plan)))
  }

  gradingInputs(slug: string): Promise<{ solution_sql?: string; hidden_tests?: string } | null> {
    return this.run(() => this.kernel.json('grading_inputs', slug))
  }

  submit(req: SubmitRequest): Promise<SubmitResponse> {
    return this.run(() => this.kernel.json<SubmitResponse>('submit', JSON.stringify(req)))
  }

  /** Free the worker's memory. The next call boots a fresh one and re-feeds the log. */
  dispose() {
    this.kernel.dispose()
    this.gen = -1
  }
}

let engine: LocalEngine | null = null

export function getEngine(): LocalEngine {
  engine ??= new LocalEngine(
    new KernelClient(
      () =>
        new Worker(new URL('../kernel/worker.ts', import.meta.url), {
          type: 'module',
        }) as unknown as KernelWorkerLike, // the DOM Worker type is wider than our protocol
    ),
  )
  return engine
}

export function setEngineForTests(e: LocalEngine | null) {
  engine = e
}
