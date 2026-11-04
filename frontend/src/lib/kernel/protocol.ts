// Messages between the main thread and the rules worker (worker.ts). Every op maps to one
// function in backend/app/kernel.py; arguments and results are JSON strings end to end.

export type KernelOp =
  | 'load_bundle'
  | 'reset_events'
  | 'add_events'
  | 'snapshot'
  | 'exercise'
  | 'quests'
  | 'submit'
  | 'grading_inputs'

export type ToKernel = { id: number; op: KernelOp; arg: string }

export type FromKernel =
  | { id: number; ok: true; result: string }
  | { id: number; ok: false; error: string }
  | { id: 0; ok: true; result: 'booted' } // sent once after Pyodide + modules are ready

/**
 * The backend files the worker mounts as the `app` package. Only pure modules: game rules,
 * grading rules, schemas, views. Never db.py, models.py, or routers.
 */
export const KERNEL_FILES = [
  'app/__init__.py',
  'app/content/__init__.py',
  'app/content/schema.py',
  'app/events/__init__.py',
  'app/events/schema.py',
  'app/game/__init__.py',
  'app/game/levels.py',
  'app/game/projection.py',
  'app/game/quests.py',
  'app/game/streaks.py',
  'app/game/submit.py',
  'app/game/unlocks.py',
  'app/game/xp.py',
  'app/grading/__init__.py',
  'app/grading/dataset.py',
  'app/grading/python.py',
  'app/grading/sql.py',
  'app/kernel.py',
  'app/schemas.py',
  'app/views.py',
] as const

/**
 * grading/sql.py and grading/dataset.py import the native `duckdb` package for the server's
 * expected-result path. The browser computes expected results with DuckDB-WASM instead, so a
 * stub module satisfies the import. Calling into it is a bug, so it raises loudly.
 */
export const BOOT_PY = `
import sys, types

def _no_duckdb(*_a, **_k):
    raise RuntimeError("native duckdb isn't available in the browser kernel")

_duck = types.ModuleType("duckdb")
_duck.connect = _no_duckdb
_duck.DuckDBPyConnection = object
sys.modules["duckdb"] = _duck
sys.path.insert(0, "/home/pyodide/kernel")

import app.kernel  # noqa: E402  (import after the stub, on purpose)
`
