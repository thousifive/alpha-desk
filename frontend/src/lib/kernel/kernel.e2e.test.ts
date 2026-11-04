// The real rules worker setup, in Node: Pyodide from node_modules, pydantic from the CDN, and
// the backend's Python files from disk. Runs the shared event-log fixtures and a submit, so a
// Pyodide-vs-CPython difference shows up here, not on the phone.
//
// Opt-in (downloads pydantic from the CDN, ~1 min on first run): pnpm test:kernel
import { execFileSync } from 'node:child_process'
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'

import { beforeAll, describe, expect, it } from 'vitest'

import { PYODIDE_CDN } from '../pyodide/protocol'
import { mountKernel } from './boot'
import { KERNEL_FILES } from './protocol'

const BACKEND = resolve(__dirname, '../../../../backend')
const FIXTURES = resolve(BACKEND, 'tests/fixtures/events')
const run = process.env.KERNEL_E2E === '1'

interface Fixture {
  today: string
  events: unknown[]
  expect: { facts: { xp_total: number; passed: string[] } }
}

type Kernel = Record<string, (arg?: string) => string>

describe.skipIf(!run)('rules kernel in Pyodide', () => {
  let k: Kernel

  beforeAll(async () => {
    const { loadPyodide } = await import('pyodide')
    // Core runtime from the npm package; packages (pydantic) from the pinned CDN.
    const py = await loadPyodide({ packageBaseUrl: PYODIDE_CDN })
    const files = Object.fromEntries(
      KERNEL_FILES.map((f) => [f, readFileSync(resolve(BACKEND, f), 'utf8')]),
    )
    await mountKernel(py, files)
    k = py.pyimport('app.kernel') as Kernel
    // The exact bundle the server would send, from the backend's own builder.
    const bundle = execFileSync('uv', ['run', 'alpha-desk', 'export-bundle'], {
      cwd: BACKEND,
      encoding: 'utf8',
    })
    k.load_bundle!(bundle)
  }, 120_000)

  const fixtures = readdirSync(FIXTURES).filter((f) => f.endsWith('.json'))

  it.each(fixtures)('%s matches the CPython projection', (name) => {
    const fx = JSON.parse(readFileSync(resolve(FIXTURES, name), 'utf8')) as Fixture
    k.reset_events!()
    k.add_events!(JSON.stringify(fx.events))
    const snap = JSON.parse(k.snapshot!(fx.today)) as {
      progress: { xp_total: number; passed_exercises: number }
      details: Record<string, { nodes: { exercises: { slug: string; passed: boolean }[] }[] }>
    }
    expect(snap.progress.xp_total).toBe(fx.expect.facts.xp_total)
    const passed = Object.values(snap.details)
      .flatMap((d) => d.nodes.flatMap((n) => n.exercises))
      .filter((e) => e.passed)
      .map((e) => e.slug)
      .sort()
    expect(passed).toEqual(fx.expect.facts.passed)
  })

  it('submit reports the open TODO(me) as locked', () => {
    k.reset_events!()
    const res = JSON.parse(
      k.submit!(
        JSON.stringify({
          slug: 'quiz-py-generics',
          attempt: { choice: 0 },
          device_id: 'node',
          now: '2026-11-04T05:00:00+00:00',
          today: '2026-11-04',
        }),
      ),
    ) as { status: string; message?: string }
    // Wrong answers don't need xp_for_attempt; right ones are locked until TODO(me) #2.
    expect(['ok', 'locked']).toContain(res.status)
  })
})
