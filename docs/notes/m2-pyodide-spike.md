# M2 spike: what runs in Pyodide

Pinned **Pyodide 314.0.7** (CPython 3.14.2, released 2026-09-14). Probed in Node with the npm
package and wheels from `cdn.jsdelivr.net/pyodide/v314.0.7/full/`.

| Check | Result |
|---|---|
| `polars` (1.33.1, in the Pyodide lockfile) | ✅ loads; `with_columns`, `.over()`, `pct_change`, lazy `filter().collect()` all work |
| `pydantic` (2.12.5) | ✅ coercion and validation work |
| `fastapi` (0.136.1) + `httpx` (0.28.1) | ⚠️ works **with a shim** (below) |
| `fastapi.testclient.TestClient` | ❌ needs threads |
| `asyncio.gather`, `asyncio.sleep` | ✅ (Pyodide's webloop) |
| `time.sleep` | ✅ blocks the worker, fine |

## FastAPI shim
Starlette runs sync endpoints and sync dependencies through `anyio.to_thread`, which fails
with `RuntimeError: can't start new thread`. The first shim (patching `run_in_threadpool`)
missed sync `yield` dependencies, which go through `contextmanager_in_threadpool`. The final
version patches `anyio.to_thread.run_sync` itself (every caller looks it up at call time),
scoped to one harness run and restored afterwards. Sync deps, `yield` deps, `HTTPException`
and `BackgroundTasks` then all work through
`httpx.AsyncClient(transport=httpx.ASGITransport(app=app))`.

The harness applies it automatically when an exercise lists `fastapi` in `packages`.
Every Python exercise is validated in both runtimes: `tests/test_python_content.py`
(CPython) and a Node + Pyodide run of the same harness.
Exercise tests must use `httpx.AsyncClient` + `ASGITransport` (async tests), not `TestClient`.

## Version skew
The backend content check runs solutions in CPython 3.12 with the backend's Polars 2.x, while
the browser has Polars 1.33. Polars exercises stick to the API that's common to both
(expressions, `group_by`, `over`, `join`, lazy frames). The content test catches breakage on
the CPython side only; check new Polars tickets in the browser too.

## Decisions taken from this
- Q1 (Polars): it loads, so the Data Pipelines branch becomes playable in M2 as planned in
  `branches.yaml`, as Python exercises with `packages: [polars]`. No backend sandbox needed.
- Q2 (FastAPI): no fallback needed; shim + async client.
