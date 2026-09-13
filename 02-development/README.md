# TopTable — League Scoreboard

A full-stack sports-league scoreboard: register teams, record match results, and see an
automatically computed league table (played, W/D/L, goals, goal difference, points).

Built for the DataTalksClub **AI Dev Tools Zoomcamp — Homework 2** (spec-first,
frontend prototype → OpenAPI contract → FastAPI backend → real database, with tests).

## Stack

- **Backend:** FastAPI · SQLAlchemy 2.0 · `uv` · database-agnostic (SQLite by default,
  set `DATABASE_URL` for Postgres etc.). OpenAPI contract in `openapi.yaml`.
- **Frontend:** React + Vite. Backend calls centralized in `frontend/src/api.js`.
- **Tests:** pytest (pure standings logic + API integration on a real DB).

## Run it

### Backend (terminal 1)

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload      # http://localhost:8000  (docs at /docs)
```

### Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

The frontend talks to the backend at `http://localhost:8000` (override with
`VITE_API_URL`).

### Tests

```bash
cd backend
uv run pytest
```

## Project layout

```
_docs/specs.md      the specification
openapi.yaml        API contract (generated from FastAPI)
backend/
  app/main.py         FastAPI app + endpoints
  app/models.py       SQLAlchemy models (Team, Match)
  app/standings.py    pure league-table computation
  tests/              standings unit tests + API integration tests
frontend/
  src/api.js          centralized backend calls
  src/App.jsx         teams / matches / standings UI
AGENTS.md           instructions for AI coding agents
```

---

## Homework 2 — answers

| # | Question | Answer |
|---|----------|--------|
| 1 | Project chosen | **Sports-league scoreboard** |
| 2 | App name | **TopTable** |
| 3 | Commit sha1 (spec commit) | `43afc5780d8781273997dacf90347473de8618a9` |
| 4 | Command to start the **frontend** | `npm run dev` (in `frontend/`) |
| 5 | Command to start the **backend** | `uv run uvicorn app.main:app --reload` (in `backend/`) |
| 6 | URL the frontend uses to reach the backend | `http://localhost:8000` |
| 7 | Command to run the **tests** | `uv run pytest` (in `backend/`) |
