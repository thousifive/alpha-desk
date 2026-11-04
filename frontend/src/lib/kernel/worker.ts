/// <reference lib="webworker" />
// The rules worker: runs backend/app/kernel.py (XP, levels, streaks, grading, views) in its
// own Pyodide, separate from the exercise worker. The exercise worker runs untrusted player
// code and gets killed on timeouts; this one holds the event log in memory and must survive.

import type { PyodideAPI } from 'pyodide'

import { PYODIDE_CDN } from '../pyodide/protocol'
import { mountKernel } from './boot'
import { KERNEL_FILES, type FromKernel, type ToKernel } from './protocol'

declare const self: DedicatedWorkerGlobalScope

// Vite inlines each file as a string at build time (`?raw`). The keys are paths relative to
// this file; strip the prefix so they match KERNEL_FILES.
const raw = import.meta.glob<string>(
  [
    '../../../../backend/app/__init__.py',
    '../../../../backend/app/{content,events,game,grading}/__init__.py',
    '../../../../backend/app/content/schema.py',
    '../../../../backend/app/events/schema.py',
    '../../../../backend/app/game/{levels,projection,quests,streaks,submit,unlocks,xp}.py',
    '../../../../backend/app/grading/{dataset,python,sql}.py',
    '../../../../backend/app/{kernel,schemas,views}.py',
  ],
  { query: '?raw', import: 'default', eager: true },
)
const PREFIX = '../../../../backend/'
const files = Object.fromEntries(Object.entries(raw).map(([k, v]) => [k.slice(PREFIX.length), v]))

const post = (msg: FromKernel) => self.postMessage(msg)

async function boot(): Promise<PyodideAPI> {
  const mod = (await import(/* @vite-ignore */ `${PYODIDE_CDN}pyodide.mjs`)) as {
    loadPyodide: (opts: Record<string, unknown>) => Promise<PyodideAPI>
  }
  const py = await mod.loadPyodide({ indexURL: PYODIDE_CDN })
  await mountKernel(py, files)
  return py
}

const ready = boot()
ready.then(
  () => post({ id: 0, ok: true, result: 'booted' }),
  () => undefined, // reported per call below
)

self.onmessage = async (ev: MessageEvent<ToKernel>) => {
  const { id, op, arg } = ev.data
  try {
    const py = await ready
    const kernel = py.pyimport('app.kernel')
    try {
      const fn = kernel[op] as (a?: string) => unknown
      // Every kernel function returns a str (or None for reset_events): no PyProxy leaks.
      const out = op === 'reset_events' ? fn() : fn(arg)
      post({ id, ok: true, result: out == null ? 'null' : String(out) })
    } finally {
      kernel.destroy()
    }
  } catch (e) {
    post({ id, ok: false, error: e instanceof Error ? e.message : String(e) })
  }
}

// Fail fast in dev if the glob and the file list drift apart.
if (import.meta.env.DEV) {
  const missing = KERNEL_FILES.filter((f) => !(f in files))
  if (missing.length) console.error('rules worker: missing kernel files', missing)
}
