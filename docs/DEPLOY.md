# Deploying Alpha Desk

Zero hosting cost: the frontend is a PWA on Netlify's free plan, and the backend runs on your
own machine behind a Cloudflare tunnel whenever it's on. Progress lives on each device and
syncs when the backend is reachable, so the backend being off is a normal state.

- Frontend: this document, "Netlify".
- Backend: "Backend" (added in Part 5).

## Netlify (frontend)

### Budget

The free plan has **300 credits a month**. A production deploy costs about **15**, and
bandwidth about **20 per GB**. When credits run out, the site is paused until next month.

What this repo does to keep that low:

| Cost | How it's kept down |
|---|---|
| Deploys | Only `main` builds. `frontend/scripts/netlify-ignore.sh` cancels deploy previews, branch deploys, and `main` commits that don't touch `frontend/`, `backend/app/` or `netlify.toml`. Docs and content-only merges don't deploy. |
| Bandwidth | Pyodide and DuckDB-WASM (the big parts: 10+ MB and 36 MB) load from jsDelivr at exact pinned versions, not from Netlify. The app shell is ~4 MB raw (~1.2 MB gzipped) per device per release, and the service worker caches it. |
| Repeat visits | `/assets/*` is hashed and cached for a year; only `index.html`, `sw.js` and the manifest revalidate. |

At ~15 credits per deploy, merging to `main` once per milestone stays far under budget.

### One-time setup

1. **Create the site.** Netlify → Add new site → Import from Git → pick the repo. Leave build
   settings empty: `netlify.toml` provides them (base `frontend`, `pnpm build`, publish `dist`).
2. **Set the API origin.** Site configuration → Environment variables → add
   `VITE_API_URL` = your tunnel origin, e.g. `https://api.example.com` (no trailing slash, no
   `/api`). The build fails on purpose if it's missing.
3. **Production branch only.** Site configuration → Build & deploy → Continuous deployment →
   Branches and deploy contexts:
   - Production branch: `main`
   - Branch deploys: **None**
   - Deploy previews: **None**

   The ignore script cancels these anyway, but turning them off in the UI means Netlify never
   even starts them.
4. **Backend CORS.** Add the site's origin to the backend's `CORS_ORIGINS`, e.g.
   `CORS_ORIGINS=https://alpha-desk.netlify.app` in `backend/.env`, and restart it.

### Deploying

Merge to `main` and push. That's the only thing that deploys.

To check a build locally first, with the same settings Netlify uses:

```sh
cd frontend
VITE_API_URL=https://api.example.com pnpm build
pnpm preview   # serves dist/; the service worker is active here, unlike in pnpm dev
```

### Pinned third-party assets

| Asset | Where | Pinned in |
|---|---|---|
| Pyodide runtime + wheels | `cdn.jsdelivr.net/pyodide/v<version>/full/` | `frontend/src/lib/pyodide/protocol.ts` |
| DuckDB-WASM (`.wasm` + worker) | `cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@<version>/dist/` | `frontend/src/lib/duckdb/cdn.ts` |
| DuckDB parquet extension | `extensions.duckdb.org/v<duckdb version>/` | follows the DuckDB-WASM version |

Each version constant must equal the npm package version in `frontend/package.json`; unit
tests fail if they drift. After the first use, the service worker serves all of these from its
cache (`pyodide`, `duckdb`, `duckdb-extensions`), so they also work offline.

### When updates reach devices

A new deploy installs in the background. The app shows **"Update available · tap to reload"**
and never reloads by itself, so a half-written exercise isn't lost. An installed PWA that stays
open also checks for updates hourly.
