# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository structure

This is a monorepo of homework submissions for the DataTalksClub **AI Dev Tools Zoomcamp**, one numbered folder per module. Each module is an independent project with its own stack, dependencies, and `.gitignore` — there is no root-level `.gitignore` or shared tooling, and nothing should be assumed to carry over between folders.

- `01-ai-native-workflow/` — Homework 1: Dataset Freshness Tracker (Django 5.2 + SQLite).
- `02-development/` — Homework 2: TopTable, a league scoreboard (FastAPI backend + React/Vite frontend).
- `03-deployment/` — Homework 3: Agent Relay, a fork of `alexeygrigorev/agent-relay` (FastAPI + PostgreSQL, Docker/Compose/Kubernetes/CI).
- `04-devops/` — Homework 4, not started yet.

`02-development` and `03-deployment` started as their own separate git clones/forks and were later flattened into this repo (their original `.git` history was not preserved). This explains why each has its own README with a "starter documentation" section still attached at the bottom.

## Commands per module

### 01-ai-native-workflow (Django)
- Install: `uv sync`
- Migrate: `uv run python manage.py migrate`
- Seed demo data: `uv run python manage.py seed_demo`
- Run dev server: `uv run python manage.py runserver` → http://127.0.0.1:8000
- Tests (all 14): `uv run python manage.py test`
- Docker: `docker compose up --build`

### 02-development (FastAPI + React)
- Backend install: `cd backend && uv sync`
- Backend run: `cd backend && uv run uvicorn app.main:app --reload` → http://localhost:8000 (docs at `/docs`)
- Backend tests: `cd backend && uv run pytest`
- Frontend install: `cd frontend && npm install`
- Frontend run: `cd frontend && npm run dev` → http://localhost:5173 (backend URL overridable via `VITE_API_URL`)
- Regenerate the OpenAPI contract after changing endpoints: `cd backend && uv run python -c "import yaml; from app.main import app; open('../openapi.yaml','w').write(yaml.dump(app.openapi(), sort_keys=False))"`
- `02-development/AGENTS.md` has this module's own conventions and git-workflow notes — read it before working inside that folder specifically.

### 03-deployment (FastAPI + PostgreSQL + Docker/Kubernetes)
- Install: `uv sync --locked`
- Run dev server (SQLite backend): `uv run uvicorn main:app --port 8000`
- Unit tests: `uv run pytest -q` (the `tests/integration/` suite is skipped unless a server is up)
- Integration tests against a running server: `RELAY_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/integration -v`
- Docker: `docker build -t agent-relay:local .` then `docker run -d -p 8000:8000 agent-relay:local`
- Compose (adds PostgreSQL): `docker compose up --build -d`
- Kubernetes (kind): `kind create cluster --config kind-config.yaml && kubectl apply -k k8s/`
- CI locally with `act`: `act push -P ubuntu-latest=catthehacker/ubuntu:act-latest`
- Full step-by-step walkthrough (including the CI/CD and rollout-gating demos): `03-deployment/README.md`

## Architecture notes

### 02-development
- Standings are always **derived** from matches at request time (`backend/app/standings.py`), never stored.
- The backend is database-agnostic via SQLAlchemy + `DATABASE_URL` (SQLite by default) — avoid SQLite-specific SQL.
- `openapi.yaml` is the contract between frontend and backend, generated from the FastAPI app; regenerate it rather than hand-editing after an endpoint change.
- All frontend → backend calls are centralized in `frontend/src/api.js`.

### 03-deployment
- Agents claim tasks from a DB through an HTTP API — there is no message broker; the DB itself is the queue. See `SPEC.md` for the full task lifecycle (`queued → processing → completed|failed`).
- `database.py` / `storage.py` are the storage seam: SQLite locally (serializes writers with `BEGIN IMMEDIATE`) vs PostgreSQL in Docker/Compose/k8s (`FOR UPDATE SKIP LOCKED` claims, plus an advisory lock so concurrent replicas can `CREATE TABLE` safely). `main.py` / `schemas.py` hold routes and request models; the HTTP protocol is meant to stay identical across both backends.
- `GET /health` is a liveness check independent of the DB; `GET /ready` checks DB connectivity and schema. They back the k8s liveness/readiness probes respectively, so a Postgres outage doesn't restart every API pod.
- `tests/integration/` is black-box HTTP testing against a live server: it's *skipped* (not failed) when `RELAY_BASE_URL` is unset, except in CI where `RELAY_REQUIRE_SERVER=1` turns a missing server into a failure instead.
- `k8s/kustomization.yaml` overrides the image tag per deploy; `.github/workflows/ci.yml` gates the `deploy` job on `test` passing first and runs `kubectl rollout undo` if the rollout itself fails.

## Git workflow

- **Always ask before running `git commit`**, even when a task clearly implies committing (e.g. "reorganize this folder"). Stage the changes, show the diff, and wait for explicit go-ahead — this overrides any module-specific instruction to the contrary (e.g. `02-development/AGENTS.md` says to commit at every step; that applies only when working inside that module on its own).
