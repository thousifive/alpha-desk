/// <reference lib="webworker" />
// Pyodide runs here, off the main thread, so a slow or looping test can't freeze the UI.
// The main thread kills this worker on timeout (see client.ts); there's no in-worker
// interrupt, which would need SharedArrayBuffer and cross-origin isolation headers.

import type { PyodideAPI } from 'pyodide'

// The same harness file the backend tests import. Vite inlines it as a string.
import harnessSrc from '../../../../backend/app/pyrunner/harness.py?raw'
import { PYODIDE_CDN, type FromWorker, type ToWorker } from './protocol'

declare const self: DedicatedWorkerGlobalScope

const post = (msg: FromWorker) => self.postMessage(msg)
let pyPromise: Promise<PyodideAPI> | null = null

async function boot(): Promise<PyodideAPI> {
  // Loaded from the CDN at runtime instead of bundled: the npm package is ~10 MB of wasm and
  // Vite doesn't need to process it. The npm dependency only provides types and pins the version.
  const mod = (await import(/* @vite-ignore */ `${PYODIDE_CDN}pyodide.mjs`)) as {
    loadPyodide: (opts: Record<string, unknown>) => Promise<PyodideAPI>
  }
  const py = await mod.loadPyodide({ indexURL: PYODIDE_CDN })
  py.globals.set('__harness_src', harnessSrc)
  py.runPython(`
import sys, types
_m = types.ModuleType("alpha_harness")
exec(compile(__harness_src, "harness.py", "exec"), _m.__dict__)
sys.modules["alpha_harness"] = _m
del _m, __harness_src
`)
  return py
}

function ensure(): Promise<PyodideAPI> {
  pyPromise ??= boot()
  return pyPromise
}

self.onmessage = async (ev: MessageEvent<ToWorker>) => {
  const msg = ev.data
  if (msg.type === 'init') {
    try {
      await ensure()
      post({ type: 'ready' })
    } catch (e) {
      pyPromise = null
      post({ type: 'init-error', message: String(e) })
    }
    return
  }

  const { id, code, tests, packages } = msg
  try {
    const py = await ensure()
    if (packages.length) {
      post({ type: 'packages', id, names: packages })
      // loadPackage is a no-op for packages already loaded in this worker.
      await py.loadPackage(packages, { messageCallback: () => undefined })
    }
    post({ type: 'started', id })
    const harness = py.pyimport('alpha_harness')
    try {
      // Calling an async Python function returns an awaitable proxy; the harness returns a
      // JSON string so no PyProxy objects leak across (they'd need manual .destroy()).
      const json = (await harness.run_tests_json(code, tests, JSON.stringify(packages))) as string
      post({ type: 'result', id, report: JSON.parse(json) })
    } finally {
      harness.destroy()
    }
  } catch (e) {
    post({ type: 'run-error', id, message: e instanceof Error ? e.message : String(e) })
  }
}
