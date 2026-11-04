Shared event-log fixtures. Each file is `{description, today, events, expect}`:

- `events` are in *arrival* order (the order a device received them), not creation order.
- `expect.facts` must hold right now (projection only).
- `expect.with_todos` needs open TODO(me)s (level_for_xp, compute_streak); tests mark those strict xfail.

Run by `backend/tests/test_projection.py` (CPython) and by `frontend/src/lib/kernel/kernel.e2e.test.ts`
(the same Python in Pyodide, opt-in with `KERNEL_E2E=1`).
