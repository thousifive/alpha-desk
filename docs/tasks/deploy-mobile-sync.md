# Task: Dashboard fixes, mobile PWA, local-first sync, and deployment

Read `CLAUDE.md` and `docs/SPEC.md` first. Start in plan mode: propose a plan, list every file
you'll create or change, call out risks and open questions, and wait for my approval before
writing code. Do this in the parts below, in order, committing after each part. Don't touch
any `TODO(me)` code.

## Goal
I want to use Alpha Desk on my iPhone and iPad whenever I have a few minutes, including in the
middle of the day, at zero hosting cost.

- **Frontend:** Netlify free tier, installable as a PWA.
- **Progress:** stored on each device (local-first) and synced when the backend is reachable.
- **Backend:** NOT a 24/7 server. I run it only during study sessions.
  - Phase 1: my current dev machine.
  - Phase 2 (later, optional): an always-on Linux laptop.
  - Both are exposed through the same Cloudflare named tunnel, so nothing changes on Netlify
    or my devices when I switch machines.
- No paid hosting, no Render, no Neon, no external database.

## Architecture
```
iPhone / iPad / desktop
  └─ React PWA (from Netlify, cached by the service worker)
       ├─ IndexedDB: event log + cached content/quests   ← source of truth for progress
       └─ when reachable ──HTTPS──► api.<mydomain> (Cloudflare named tunnel)
                                        └─► dev machine now / Linux laptop later
                                              Docker Compose → FastAPI + SQLite
```

What works with the backend off: dashboard, XP/levels/streaks, daily quests (pre-cached),
SQL exercises (DuckDB-WASM), Python exercises (Pyodide), flashcards, quizzes.

What needs the backend: AI hints, PM Chat, boss-fight grading, Interview Arena, generating new
quests beyond the cached window, and syncing between devices.

---

## Part 0: Dashboard fixes (do first)
1. Map each boss to its branch in `docs/SPEC.md` and fix the dashboard. The SQL & OLAP boss
   must not be "The Oracle" (that's Agents & LLMs). Suggested mapping:
   - SQL & OLAP → "The Analytics Desk"
   - Python & FastAPI → "The API Gateway"
   - Data Pipelines → "The Data Feed"
   - Agents & LLMs → "The Oracle" (MCP server), then "The Copilot" (LangGraph agent)
   - Cloud & DevOps → "Go Live"
   - Buy-Side Finance → "The PM Review"
   Propose a better mapping if you see one.
2. Make counts consistent and labelled everywhere: "nodes" vs "exercises". The boss card, the
   skill tree, and the node grid must use the same numbers and words.
3. Restyle "offline" feature states as **locked**, not broken: amber/grey with a padlock icon,
   in-story copy (e.g. "Lena: the level system is waiting on your PR"), naming the TODO(me)
   task, its file, and its function. No red error text for expected locked states.

## Part 1: Local-first progress (IndexedDB + event log)
1. **Storage:** IndexedDB via Dexie. Don't use localStorage for progress, because it's too
   small and blocks the UI. Tables:
   - `events`: the append-only log
   - `cache`: content YAML, quests, flashcards due, last known server-derived data
   - `meta`: device_id, last sync cursor, last synced time
2. **Event log is the source of truth.** Every attempt, flashcard review, hint used, XP award,
   quest completion, and achievement is an event:
   `{ id: uuid, device_id, type, payload, created_at }`. Events are never updated or deleted.
3. **Derived state on the client:** XP, level, streak, node progress, and SM-2 schedules are
   computed from the event log (memoized/incremental). Streaks use each event's `created_at`
   in my local timezone (Asia/Kolkata), never sync time.
4. **Shared logic:** where the backend also needs derived state (weekly report, AI context),
   keep the rules identical. Either mirror them with shared test fixtures that both the TS and
   Python test suites run against, or explain a better approach.
5. **Resilience:**
   - Call `navigator.storage.persist()` on first run.
   - Never discard unsynced events.
   - Settings → "Export my progress" (JSON download of all events) and "Import" (merge by
     event id). This is the manual backup in case iOS clears site data after long inactivity.
6. **Tests:** derived XP/level/streak from fixture event logs, a streak spanning offline days
   that synced late, and import/export round-trip.

## Part 2: Sync with an intermittent backend
1. **Detecting the server:** poll `GET /health` on app open, on window focus, and every 60s
   while the app is visible. Back off when it's unreachable. No error spam in the console or UI.
2. **Sync flow when reachable:**
   1. POST unsynced events in batches (e.g. 200 per request).
   2. GET events since my last sync cursor, which include events from my other devices.
   3. Merge into IndexedDB by event id, recompute derived state, and update the cursor.
   4. Refresh the cache: pre-generate and store the **next 3 days of daily quests** and the
      flashcards due in that window, so the next day works offline.
3. **Backend:**
   - `events` table with a unique constraint on event id. Ingestion is idempotent.
   - `POST /sync/events` and `GET /sync/events?since=<cursor>`.
   - The backend keeps its own derived tables for AI features and the weekly report.
   - **TODO(me):** `ingest_events(batch)`, which validates each event with Pydantic, skips
     duplicates by id, inserts the rest in one transaction, and returns
     `{accepted, duplicates, rejected}`. Write the tests first, plus a one-line note on what it
     teaches (idempotent ingestion, the same pattern as ETL loads).
4. **UI:**
   - A header status pill: "Synced · 2h ago" / "Offline · 14 changes queued" / "Syncing…",
     in calm amber/grey styling.
   - AI buttons (hints, PM Chat, grading, Interview Arena) show "Available when the server is
     on" while offline, instead of failing.
5. **Auth while offline:** a long-lived session (30 days) so the PWA never asks me to log in
   while the server is off. Login only needs the server on first use or after expiry.
6. **Tests:** batch dedupe on the backend, merging events from two devices, sync resuming after
   an interrupted batch, and quests pre-generated for offline days.

## Part 3: PWA + mobile UX
1. Web app manifest (name "Alpha Desk", dark theme, standalone display), icons including
   `apple-touch-icon`, and iOS meta tags so "Add to Home Screen" opens full-screen.
2. Service worker (vite-plugin-pwa / Workbox):
   - Precache the app shell.
   - Runtime-cache Pyodide, DuckDB-WASM, content YAML, and the fund dataset, so each device
     downloads them once.
   - Show an "Update available, tap to reload" toast on new versions.
3. Responsive layouts:
   - **iPhone:** dashboard, daily quests, flashcards, quizzes, PM Chat, and short SQL
     exercises. Simplified editor (larger font, a toolbar with Run/Submit). Long Python
     exercises show "Best on iPad/desktop" but stay usable.
   - **iPad:** the full experience. The editor sits beside the prompt/results in landscape and
     stacks in portrait. Cmd+Enter / Cmd+Shift+Enter work on a hardware keyboard.
   - Touch targets ≥ 44px, safe-area insets respected, no horizontal scroll.
4. Test with Playwright device emulation (iPhone 15, iPad Pro 11"), and give me screenshots of
   the dashboard, an SQL exercise, and flashcards on each.

## Part 4: Netlify frontend (free tier, credit-conscious)
The free plan is 300 credits/month, with ~15 credits per production deploy and ~20 credits/GB
of bandwidth. If credits run out, the site is paused until next month.
1. `netlify.toml`: build command, publish dir, SPA fallback (`/* /index.html 200`), and
   long-lived cache headers for hashed assets, Pyodide, and DuckDB-WASM.
2. Deploy **only from `main`**. Document turning off deploy previews and branch deploys in the
   Netlify UI, or disable them in config where possible. I'll merge to `main` only at milestones.
3. API base URL from `VITE_API_URL`, with no hardcoded URLs. Provide `.env.example`.
4. Self-host the Pyodide and DuckDB-WASM assets, or pin exact CDN versions.

## Part 5: Backend self-hosting (portable, intermittent)
The backend must be machine-agnostic. Moving from the dev machine to the Linux laptop must need
no code changes and no Netlify changes.
1. `docker-compose.yml`: `restart: unless-stopped`, SQLite on a mounted volume
   (`./data/alpha.db`), env vars from `backend/.env`, port bound to `127.0.0.1:8000` only.
   Must work the same on macOS (Docker Desktop/OrbStack) and Linux.
2. SQLite in WAL mode, with migrations run on startup (pick Alembic or SQLModel create_all and
   explain why).
3. `make backup`: back up with the SQLite backup API (not a raw file copy) to `./backups`,
   keeping the last 14. Also run it automatically when `make serve` stops.
4. `GET /health`: status, version, DB connectivity, and the hostname of the machine serving it.
5. **Cloudflare named tunnel** at a stable hostname `api.<mydomain>`:
   - Document the one-time setup: `cloudflared tunnel create alpha-desk`, the config file, and
     the DNS route.
   - Phase 1: `make serve` starts Docker Compose and the tunnel together on the dev machine,
     and stops both on Ctrl+C. Include the macOS `caffeinate -s` tip to keep the machine awake
     during a session.
   - Phase 2: the same tunnel credentials run as a systemd service on the Linux laptop.
   - Optional: Cloudflare Access in front of the API, restricted to my email.
6. **Security:**
   - CORS allows only my Netlify domain (and localhost in dev), set via an env var.
   - Keep the app password login. Choose cross-origin-safe auth (secure httpOnly SameSite=None
     cookies vs bearer token in IndexedDB) and explain the choice.
   - The Anthropic API key exists only in `backend/.env`, never in the frontend or the repo.
   - Rate limiting on auth and AI endpoints.

## Part 6: Local dev and migration
1. `make dev`: backend on `0.0.0.0:8000` plus Vite with `--host`, printing the LAN URL for
   testing on phone/iPad over home Wi-Fi. Note in the README that the Netlify HTTPS frontend
   can't call a plain-HTTP LAN backend (mixed content), so use the tunnel for that.
2. `docs/MIGRATION.md`: step-by-step move to the Linux laptop. Install Docker and cloudflared,
   clone the repo, copy `data/alpha.db`, `backend/.env`, and the tunnel credentials, start the
   services, enable the systemd units, verify `/health` shows the new hostname, then stop the
   tunnel on the dev machine. Include a rollback step.

## Part 7: Docs
1. `docs/SPEC.md`: replace the old deployment target with this architecture, and add the
   local-first/sync model, the boss-to-branch mapping, and the mobile UX rules.
2. `README.md`: step-by-step guides for (a) local dev, (b) `make serve` with the tunnel,
   (c) Netlify setup including credit-saving settings, (d) installing the PWA on iPhone/iPad,
   and (e) export/import backup.
3. `CLAUDE.md`: update the Commands section (`make dev`, `make serve`, `make backup`, tests, lint).

## Definition of done
- The dashboard shows the correct boss per branch, consistent counts, and locked (not red)
  states for pending TODO(me) features.
- I can install Alpha Desk on my iPhone and iPad from the Netlify URL and log in.
- **With the backend off all day**, I can do daily quests, SQL exercises, and flashcards on my
  phone, and XP and streaks update immediately.
- When I start `make serve` that evening, my phone's events sync, the iPad then shows the same
  progress, and there are no duplicates.
- Cached quests cover the next 3 days without the server.
- `https://api.<mydomain>/health` works through the tunnel, and port 8000 isn't exposed any
  other way.
- Export and import of progress round-trip correctly.
- All tests pass. List the manual checks I should run on each device, and which TODO(me)
  tasks are waiting for me.
