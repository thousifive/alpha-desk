# Alpha Desk: Product Spec

A gamified learning app for becoming an AI full-stack engineer at a hedge fund.

## 1. Who it's for
A single user: a senior frontend engineer (8+ years: React, TypeScript, Redux, Next.js, D3) who
has built MCP server integrations and agentic workflows with the Claude API, and works on trading
UIs at an investment bank. The goal is to qualify for a role building LLM-powered tools for hedge
funds. The weaker skills the app must train:

- Production Python + FastAPI (async, Pydantic, dependency injection, pytest)
- SQL beyond CRUD (window functions, CTEs, time-series aggregation)
- Polars (and some Pandas), OLAP databases (DuckDB first, then ClickHouse)
- ETL pipelines for financial market data (incremental loads, idempotency, validation)
- LangGraph, RAG, text-to-SQL agents, LLM evals
- Cloud deployment (AWS or GCP, Docker, CI)
- Buy-side finance vocabulary and thinking (exposures, factors, Sharpe, drawdown, PnL attribution)

The user learns best by building and playing. The app should be something they want to open every day.

## 2. Core concept and narrative
The player is a newly hired "AI engineer" at a fictional hedge fund, **Meridian Capital**
(fictional; never use real fund names). Fictional colleagues send requests:

- **Priya (Portfolio Manager):** non-technical, impatient, asks business questions
- **Marcus (Quant Analyst):** asks data and analytics questions
- **Lena (Head of Engineering):** reviews code, asks about architecture and reliability

Every lesson is framed as a ticket or request from one of them. The campaign's arc is building
the fund's "Research Copilot", a real working project in the user's own repo, and the game
tracks progress on it.

## 3. Game mechanics
1. **Skill tree.** Six branches: Python & FastAPI, SQL & OLAP, Data Pipelines (Polars/ETL),
   Agents & LLMs (LangGraph/RAG/MCP/evals), Cloud & DevOps, Buy-Side Finance. Nodes unlock in
   dependency order. Render it as an interactive D3 graph with locked, available, and mastered states.
2. **XP and levels.** Titles: Intern → Analyst → Associate → VP → Director → Partner.
   XP comes from quests, exercises, streaks, and boss fights. Show a level-up animation.
3. **Daily quests.** Three short tasks a day (15–30 min total), mixed across branches. The mix
   is weighted toward the weakest skills, based on accuracy data.
4. **Streaks**, with one "freeze" token earned per 7-day streak. Missed days aren't punished harshly.
5. **Boss fights = capstone milestones.** Each branch ends with a boss (Agents & LLMs has
   two, fought in order), which is a real build milestone of the Research Copilot. The source
   of truth is `content/branches.yaml`; the dashboard shows the next boss of each branch.

   | Branch | Boss | What you build |
   |---|---|---|
   | SQL & OLAP | The Analytics Desk | DuckDB queries for returns, rolling drawdown, sector exposure |
   | Python & FastAPI | The API Gateway | typed, tested FastAPI endpoints serving those numbers |
   | Data Pipelines | The Data Feed | a Polars ETL loading daily prices into DuckDB, idempotently |
   | Agents & LLMs | The Oracle, then The Copilot | an MCP server over the market DB and SEC filings; a LangGraph text-to-SQL + RAG agent |
   | Cloud & DevOps | Go Live | deploy the Research Copilot with Docker and CI |
   | Buy-Side Finance | The PM Review | walk Priya through exposures, Sharpe, drawdown, PnL attribution |

   The user submits a GitHub repo URL or a pasted diff. The AI reviewer (Lena) grades it against
   a rubric and either passes it or returns specific fixes.
6. **Market Mode (finance flashcards).** Spaced repetition (SM-2) for buy-side concepts,
   including small numeric problems (e.g. "Compute Sharpe from these returns").
7. **PM Chat (communication practice).** A Claude-powered roleplay where Priya asks a vague
   business question. The user clarifies requirements and explains a technical result in plain
   English. It's scored on clarity, jargon avoidance, and question quality.
8. **Interview Arena.** Timed mock rounds: system design (e.g. "design a natural-language query
   layer over portfolio data, with SQL guardrails and hallucination checks"), Python live coding,
   SQL puzzles, and behavioral questions. AI scoring with written feedback.
9. **Achievements**, e.g. "First idempotent pipeline", "Window function wizard", "Zero
   hallucinated numbers in an eval run", "7-day streak".
10. **Weekly report.** XP gained, branch progress, weakest topics, and a suggested focus for next week.

## 4. Exercise types
- **Python:** runs in **Pyodide** in a web worker with hidden pytest-style tests. Shows
  pass/fail per test and stdout.
- **SQL:** runs in **DuckDB-WASM**, preloaded with a realistic fictional dataset: ~50 tickers,
  3 years of daily OHLCV, a sample long/short portfolio with positions and trades, and
  sector/factor tags. The result set is compared with the expected output.
- **Polars:** runs in Pyodide if supported. Otherwise it runs on a sandboxed backend endpoint
  with timeouts and resource limits.
- **Concept quizzes:** multiple choice, with explanations.
- **Code review challenges:** the user is shown a flawed FastAPI endpoint or ETL job and must
  find the bugs (e.g. non-idempotent upsert, a blocking call in async code, a SQL injection in
  text-to-SQL).
- **Hints:** three levels (nudge → approach → near-solution). Using hints reduces XP. Hints are
  generated by Claude with the exercise context and must never reveal the hidden tests.

## 5. Curriculum content
All content is data-driven, stored as YAML in `/content`.

- **Python & FastAPI:** typing, dataclasses vs Pydantic, async/await, routing, dependencies,
  background tasks, error handling, pytest + httpx testing.
- **SQL & OLAP:** joins, CTEs, window functions (LAG, rolling averages, RANK), time-series
  bucketing, row vs columnar storage, DuckDB specifics, a ClickHouse intro.
- **Data Pipelines:** Polars lazy API, expressions, time-series joins, missing and late data,
  schema validation (Pandera or Pydantic), incremental and idempotent loads, scheduling.
- **Agents & LLMs:** tool use, MCP server design, LangGraph state/nodes/edges/checkpointing,
  RAG (chunking, embeddings, retrieval, citations), text-to-SQL guardrails (read-only role,
  allow-listed tables, query validation), evals (golden questions, numeric accuracy checks).
- **Cloud & DevOps:** Docker, environment config, managed Postgres/object storage, GitHub
  Actions CI, logging and basic observability.
- **Buy-Side Finance:** long/short, gross vs net exposure, beta, factor exposure, Sharpe/Sortino,
  max drawdown, PnL attribution, what PMs, analysts, and risk teams do, research workflows.

Target: 8–12 nodes per branch, 3–6 exercises per node. For M1, the SQL & OLAP branch is fully
built with real exercises and tests. Other branches get a node structure and 1–2 exercises each.
An admin "generate exercise with Claude" tool writes draft content into `/content` for review.

## 6. Tech stack
- **Frontend:** React + TypeScript + Vite, TanStack Query, Tailwind, D3 (skill tree, charts),
  Monaco editor, Framer Motion (XP pops, level-ups).
- **Backend:** Python 3.12, FastAPI (async), Pydantic v2, SQLModel, SQLite (WAL mode) with
  Alembic migrations, pytest, `uv` for dependencies.
- **Local-first client:** Dexie (IndexedDB) event log, a Pyodide "rules kernel" running the
  backend's pure-Python game rules in a web worker, vite-plugin-pwa (Workbox).
- **AI:** Claude API (Anthropic Python SDK) for hints, grading, PM Chat, and interview scoring.
  A LangGraph multi-step grader: fetch repo/diff → run checks → apply rubric → write feedback.
  Prompts are kept in versioned files under `backend/prompts/`.
- **MCP:** an MCP server exposing progress tools: `get_my_weak_topics`, `get_today_quests`,
  `log_study_session`.
- **Infra:** see §7, Deployment. Zero hosting cost: no paid hosting, no external database.
- Single-user app with a single password.

## 7. Deployment and sync

**Shape.** The frontend is a PWA on Netlify's free plan (public). The backend is *not* a 24/7
server: it runs on the player's own machine (`make serve` on the Mac during study sessions;
later an always-on Linux laptop under systemd). "Server off" is a normal state, not an error.
Details: `docs/DEPLOY.md`, `docs/MIGRATION.md`.

```
  Netlify (public)                       player's tailnet (private)
  ┌──────────────────┐   app shell   ┌────────────────────────────────────────────────────┐
  │ PWA: HTML/JS/CSS │──────────────▶│ iPhone / iPad / desktop (Tailscale app on)          │
  └──────────────────┘               │   IndexedDB event log · Pyodide rules kernel        │
                                     │        │ HTTPS, bearer token, only when reachable   │
                                     │        ▼                                            │
                                     │ https://alpha-desk.<tailnet>.ts.net  (tailscale     │
                                     │        │                              serve, no     │
                                     │        ▼                              Funnel)       │
                                     │ 127.0.0.1:8000  FastAPI (Docker) ── SQLite (WAL)    │
                                     │                 ./data/alpha.db · ./backups (14)    │
                                     └────────────────────────────────────────────────────┘
```

**Private API.** The API is reachable only from the player's own devices on their Tailscale
network: `tailscale serve` terminates HTTPS (a Let's Encrypt cert for the `ts.net` name) and
proxies to the backend on loopback. Tailscale Funnel is never used, and the backend port is
never published beyond `127.0.0.1`. From any device not on the tailnet the name doesn't
resolve. The Tailscale machine name (`alpha-desk`) is the stable part of the URL; moving the
backend to another machine moves the name, not the URL. When Tailscale is off on a device, the
app behaves exactly as if the server were off.

**Local-first model.**
- Each device stores progress as an append-only **event log** in IndexedDB (Dexie): `attempt`,
  `xp_awarded`, `quest_completed`, `flashcard_reviewed`, `hint_used`, `achievement_unlocked`.
  Events are `{id: uuid, device_id, type, payload, created_at, local_date}` and are never
  updated or deleted. The log is the source of truth.
- XP, level, streaks, node progress and SM-2 schedules are **derived** from the log. The rules
  are written once in Python (`backend/app/game/`, pure functions) and run in the browser via
  Pyodide, so client and server can't drift.
- Streaks use each event's `local_date` (the player's zone when it happened), never sync time,
  so a streak kept offline counts once it syncs.
- XP awards are deduplicated by a `ref_key`, so the same exercise passed on two devices offline
  pays out once.
- Settings → Export/Import (JSON, merged by event id) is the manual backup if iOS clears site
  data. The app asks for persistent storage on first run.

**Sync protocol** (`/api/sync/*`, idempotent and safe to interrupt):
1. Push unsynced events, oldest first, in batches of 200. The server dedupes by event id and
   numbers each new event with an increasing `seq`.
2. Pull everything after the device's cursor (`seq`), 500 per page; the cursor moves only after
   a page is stored. Merge by event id.
3. Cache quest plans for today + 2 days, and the content bundle, so the next 3 days work with
   the server off.
4. The server projects synced events into its own tables (attempts, XP ledger, quests) for
   server-side features (weekly report, AI context).

Sync runs when the server becomes reachable, a few seconds after local changes, and every 3
minutes while up. A server must never start on an older copy of its database than devices
have synced with (cursors would skip new events; see `docs/MIGRATION.md`).

**Auth.** One password. Login returns a signed 30-day bearer token stored in IndexedDB and
refreshed daily, because Safari blocks the cross-site cookies a Netlify-to-backend session
would need (`*.netlify.app` and `*.ts.net` are different sites). CORS allows only the
configured origins, without credentials, and answers Chrome's Private Network Access
preflight (`Access-Control-Allow-Private-Network: true`) because the tailnet address is
private. Failed logins are rate-limited. The password stays as a second layer on top of
tailnet membership.

## 8. Data model (starting point)
User, SkillNode (branch, prerequisites, xp_reward), Exercise (type, node_id, prompt,
starter_code, tests, difficulty), Attempt (exercise_id, code, passed, hints_used, duration, xp),
Quest (date, exercise_ids, status), BossFight (node_id, rubric, submissions), Submission
(repo_url/diff, grade, feedback), Flashcard + ReviewState (SM-2 fields), Achievement +
UserAchievement, Streak, ChatSession (persona, transcript, scores).

Sync adds SyncEvent (seq, id, device_id, type, payload, created_at, local_date) and a
SyncState cursor for the server-side projections. Rows projected from synced events carry the
source `event_id`.

## 9. UX requirements
- A dark, fast "trading terminal" look. The home dashboard shows today's quests, streak, level
  progress, a skill-tree mini-map, and the next boss.
- Exercise screen: the prompt framed as a colleague's ticket, an editor, Run, test results,
  hints, and Submit with satisfying XP feedback.
- Keyboard-first: Cmd+Enter runs, Cmd+Shift+Enter submits.
- Mobile is first-class (installable PWA, works offline):
  - **iPhone:** dashboard, daily quests, flashcards, quizzes, PM Chat, short SQL exercises.
    The editor uses a 16 px font (no iOS zoom), word wrap, no autofocus on touch, and a
    Run/Submit toolbar. Long Python exercises say "Best on iPad/desktop" but stay usable.
  - **iPad:** the full experience. Editor beside prompt and results in landscape, stacked in
    portrait. Cmd+Enter / Cmd+Shift+Enter work on a hardware keyboard.
  - Below the `lg` breakpoint, navigation is a bottom tab bar.
  - Touch targets ≥ 44 px on coarse pointers, safe-area insets respected, no horizontal page
    scroll (wide result tables scroll inside their panel).
  - Server-dependent features show a **locked** state (amber/grey, padlock, in-story copy naming
    the pending TODO(me)), never red error text. "Server off" is shown as a calm sync pill.
  - New versions wait for the player: "Update available · tap to reload", never a forced reload.

## 10. Non-functional requirements
- The Anthropic API key is stored server-side only.
- Backend code execution is sandboxed: subprocess, time and memory limits, no network.
- AI hints are cached per exercise and hint level. Monthly token usage is shown in settings.
- Tests cover XP/level logic, SM-2 scheduling, quest generation, and exercise grading.
- Offline: with the backend off all day, quests, SQL exercises and flashcards work on a phone,
  and XP and streaks update immediately. No duplicated events or XP after sync.
- Zero hosting cost. The API is never public: tailnet only via `tailscale serve`, no Funnel.

## 11. Milestones
- **M1:** skeleton + auth + dashboard + the SQL branch fully playable in DuckDB-WASM, with XP and levels
- **M2:** Python exercises via Pyodide + daily quests + streaks
- **M2.5:** dashboard fixes, local-first event log + sync, installable PWA and mobile layouts,
  Netlify frontend, self-hosted Docker backend (task: `docs/tasks/deploy-mobile-sync.md`)
- **M3:** flashcards (SM-2) + achievements + the skill tree graph
- **M4:** Claude hints + PM Chat
- **M5:** boss fights with the LangGraph grader + Interview Arena
- **M6:** MCP server + weekly report (app deployment moved to M2.5)

### Definition of done for M1
The user can log in, see the dashboard, open the SQL branch, solve at least 15 SQL exercises
against the seeded fund dataset in the browser, earn XP, level up, and see progress persist
after a reload.
