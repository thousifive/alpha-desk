# Task: Switch backend access from Cloudflare Tunnel to Tailscale (frontend stays on Netlify)

## Context
The previous task (`docs/tasks/deploy-mobile-sync.md`) planned to expose the backend through a
Cloudflare named tunnel. I've decided to use **Tailscale** instead:

- **Frontend:** stays on **Netlify** (public, always loads, installable PWA).
- **Backend API:** reachable **only from my own devices** over my tailnet, via
  `tailscale serve` with HTTPS at `https://<machine>.<tailnet>.ts.net`.
- No Cloudflare tunnel, no Cloudflare Access, no custom domain.
- Everything else from the previous task stays: local-first IndexedDB event log, sync when
  the backend is reachable, intermittent backend (only on during study sessions), PWA, mobile UX.

During that task I asked for the Cloudflare tunnel to be skipped and a **Tailscale
placeholder** left instead (e.g. a TODO in `make serve`, a stub script, or a docs section).
This task fills in that placeholder. Some Cloudflare pieces may still have been created before
the change of plan, so check for both.

That task may be fully done, partly done, or have gone differently from its spec. **Adapt to
what actually exists in the repo. Don't assume.**

## Step 1: Audit first (plan mode, no code changes)
Read `CLAUDE.md`, `docs/SPEC.md`, `docs/tasks/deploy-mobile-sync.md`, and the current code.
Then report back with:
1. What from the previous task is implemented, partly implemented, or missing (Parts 0–7).
2. Every Tailscale placeholder or TODO (where it is and what it expects), and every leftover
   Cloudflare reference: code, Makefile targets, compose files, scripts, env vars, docs
   (README, SPEC, CLAUDE.md, MIGRATION.md), and comments.
3. How the frontend finds the API (env var name, default, fallbacks), and how auth works
   (cookies vs bearer token), since this decides the CORS/cookie changes below.
4. Any failing tests or unfinished parts I should know about before switching.
5. A concrete plan for Steps 2–6, adjusted to what you found, with files to change.

Wait for my approval before changing anything. If the previous task is still incomplete in
ways that block this one, say so and propose whether to finish it first or fold it in here.

## Step 2: Fill in the Tailscale placeholder
1. Replace the placeholder(s) with the working setup below, and remove any leftover
   Cloudflare tunnel setup (config, credentials handling, Makefile targets, systemd units,
   docs). Don't leave dead config or stale TODOs behind.
2. `make serve` should:
   - start the backend (Docker Compose, port bound to `127.0.0.1:8000` only)
   - check that Tailscale is installed and logged in (`tailscale status`), and fail with a
     clear message if not
   - run `tailscale serve --bg 8000` (or check it's already configured), so the backend is
     served over HTTPS at the tailnet hostname
   - print the HTTPS URL and hit `/health` through it to confirm it's working
   - on Ctrl+C: stop the backend, run the backup, and leave or reset `tailscale serve` (your
     call; explain it)
   - keep the macOS `caffeinate -s` tip (or run it automatically while serving, if you think
     that's better)
3. `make serve-status`: show whether the backend, Tailscale, and `tailscale serve` are up, plus
   the URL.
4. **Never** use Tailscale Funnel. The API must not be public.
5. Keep the app password login as a second layer of security.

## Step 3: Frontend ↔ API across origins (Netlify → ts.net)
1. The frontend reads the API base URL from `VITE_API_URL`, set in Netlify to
   `https://<machine>.<tailnet>.ts.net`. Keep `.env.example` updated. Local dev keeps its own default.
2. CORS: allow only my Netlify domain (and localhost in dev), from an env var. Allow
   credentials if auth uses cookies.
3. **Chrome Private Network Access:** a public site calling a `100.x` tailnet address can be
   blocked by desktop Chrome. Handle preflights by returning
   `Access-Control-Allow-Private-Network: true` when the request asks for it. Add a test.
4. **Auth across origins:** review the current approach. Cookies would need `SameSite=None;
   Secure`, and Safari's third-party cookie blocking may break them, because the Netlify app
   and the `ts.net` API are different sites. If cookies won't be reliable on iOS Safari and
   the installed PWA, switch to a bearer token stored in IndexedDB, sent in the
   `Authorization` header, with a 30-day lifetime. Explain the decision and its trade-offs.
5. Offline and "server unreachable" behavior must not change. When Tailscale is disconnected
   on the phone, the app behaves exactly as if the server is off: local progress keeps
   working, events queue, the status pill shows offline, and AI buttons say "Available when
   the server is on."
6. Improve the status pill copy, if it's cheap to do, so I can tell apart:
   "Offline · server not reachable (is Tailscale on?)" vs "Synced · 2h ago".

## Step 4: Moving to the Linux laptop later
Rewrite `docs/MIGRATION.md` (or create it) for Tailscale:
1. Install Docker and Tailscale on the Linux laptop, and log in to the same tailnet.
2. Clone the repo, copy `data/alpha.db` and `backend/.env`, and start with Docker Compose as a
   systemd-managed service (or `restart: unless-stopped` plus Docker enabled at boot).
3. Run `tailscale serve --bg 8000` there, and make sure it persists across reboots.
4. **Keep the URL stable:** document the two options and recommend one.
   (a) Give the Linux laptop the MacBook's old Tailscale machine name (rename or remove the
       Mac's node first), so `VITE_API_URL` doesn't change.
   (b) Update `VITE_API_URL` in Netlify and redeploy once.
5. Verify `/health` shows the new hostname from my iPhone over mobile data.
6. Rollback: start serving from the Mac again.

## Step 5: Docs
1. `docs/SPEC.md`: update the architecture diagram and deployment section. Replace Cloudflare
   with Tailscale, and note that the API is private to my tailnet.
2. `README.md`:
   - one-time Tailscale setup: account, install on the Mac, enable MagicDNS and HTTPS
     certificates in the admin console
   - installing the Tailscale app on iPhone/iPad, and enabling VPN On Demand so it reconnects
     automatically
   - setting `VITE_API_URL` in Netlify
   - the daily routine: `make serve` when studying, and the phone works offline in between
   - troubleshooting: "offline" on phone (check Tailscale is connected), CORS/PNA errors on
     desktop Chrome, an expired HTTPS cert, the Mac asleep
3. `CLAUDE.md`: update the Commands section (`make dev`, `make serve`, `make serve-status`,
   `make backup`, tests, lint), and add the rule "the API is never exposed publicly; no
   Tailscale Funnel."
4. Add a short note to the end of `docs/tasks/deploy-mobile-sync.md` saying the Cloudflare
   parts are superseded by this task.

## Step 6: Verify
1. Run all tests and lint.
2. Tests for CORS (allowed vs disallowed origin), the PNA preflight header, and auth working
   cross-origin with the chosen method.
3. Give me a manual checklist:
   - The Mac runs `make serve`. The iPhone on **mobile data** with Tailscale on opens the
     Netlify PWA, logs in, completes an SQL exercise, and the event syncs.
   - With Tailscale off on the phone, I can do flashcards and quests offline, the status pill
     shows offline, and turning Tailscale back on syncs everything with no duplicates.
   - The iPad shows the same progress after syncing.
   - With the Mac off, the PWA still opens and works offline on both devices.
   - From a device **not** on my tailnet, the API URL doesn't resolve or connect.

## Definition of done
- No Tailscale placeholders or Cloudflare references remain, except the superseded note.
- The API is reachable only over my tailnet with HTTPS. The frontend is on Netlify.
- Cross-origin auth works reliably on iOS Safari and the installed PWA.
- The offline/local-first behavior is unchanged and all its tests still pass.
- The docs are updated and the manual checklist is provided.
- List any TODO(me) tasks still waiting for me.
