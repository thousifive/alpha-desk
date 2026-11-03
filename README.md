# Alpha Desk

A gamified learning app for becoming an AI full-stack engineer at a hedge fund.

You play a new AI engineer at **Meridian Capital**, a fictional fund. Colleagues send you
tickets, and solving them teaches Python, FastAPI, SQL, Polars, DuckDB, LangGraph, RAG, MCP,
cloud deployment, and buy-side finance. You earn XP, level up from Intern to Partner, keep
streaks, and beat "boss fights" that are real milestones of a working Research Copilot.

> Status: in development. See `docs/SPEC.md` for the full spec and milestones.

## Features
- Skill tree with six branches and unlockable nodes
- Daily quests weighted toward your weakest skills
- In-browser SQL (DuckDB-WASM) and Python (Pyodide) exercises with hidden tests
- Finance flashcards with spaced repetition (SM-2)
- PM Chat: practice explaining technical results to a non-technical portfolio manager
- Interview Arena: timed mock interviews with AI feedback
- Boss fights graded by an AI code reviewer
- MCP server so you can query your progress from Claude

## Tech stack
- **Frontend:** React, TypeScript, Vite, Tailwind, TanStack Query, D3, Monaco
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLModel, pytest, uv
- **AI:** Claude API, LangGraph, MCP

## Project structure
```
alpha-desk/
├── CLAUDE.md      # rules for Claude Code
├── README.md
├── docs/SPEC.md   # full product spec
├── frontend/      # React app
├── backend/       # FastAPI app
└── content/       # YAML curriculum
```

## Getting started
<!-- Fill in after M1 (ask Claude Code to write setup and run instructions) -->

### Prerequisites
- Node.js (LTS)
- Python 3.12 and `uv`
- An Anthropic API key (needed from M4 onward)

### Setup
```bash
# TBD after M1
```

### Environment variables
Create `backend/.env`:
```
ANTHROPIC_API_KEY=your-key-here
```

## Roadmap
- [ ] M1: Dashboard, XP and levels, full SQL branch
- [ ] M2: Python exercises, daily quests, streaks
- [ ] M3: Flashcards, achievements, skill tree graph
- [ ] M4: AI hints, PM Chat
- [ ] M5: Boss fights, Interview Arena
- [ ] M6: MCP server, deployment, weekly report
