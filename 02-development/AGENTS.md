# AGENTS.md — instructions for AI coding agents

**TopTable** — a sports-league scoreboard. DataTalksClub AI Dev Tools Zoomcamp,
Homework 2.

## Shape

- `backend/` — FastAPI + SQLAlchemy, managed with `uv`. Database-agnostic via
  `DATABASE_URL` (SQLite default). Standings logic is pure (`app/standings.py`).
- `frontend/` — React + Vite. All backend calls centralized in `src/api.js`.
- `_docs/specs.md` — the spec. `openapi.yaml` — the API contract (source of truth
  between frontend and backend).

## Commands

- Backend deps: `cd backend && uv sync`
- Backend run: `cd backend && uv run uvicorn app.main:app --reload` (→ http://localhost:8000)
- Backend tests: `cd backend && uv run pytest`
- Frontend deps: `cd frontend && npm install`
- Frontend run: `cd frontend && npm run dev` (→ http://localhost:5173)
- Regenerate the contract: `cd backend && uv run python -c "import yaml; from app.main import app; open('../openapi.yaml','w').write(yaml.dump(app.openapi(), sort_keys=False))"`

## Conventions

- Standings are always **derived** from matches, never stored.
- Keep the backend database-agnostic (SQLAlchemy; no SQLite-specific SQL).
- Write/adjust tests with every behavior change; keep `uv run pytest` green.

## Git workflow

- Commit at every meaningful step with a clear message.
- `git add -A && git commit -m "<what changed>"`.
- Never commit `.venv/`, `node_modules/`, `frontend/dist/`, or `*.db` (see `.gitignore`).
