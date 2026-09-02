# Dataset Freshness Tracker

A small Django app that answers one question a data team asks constantly:
**which of our datasets are stale or failing right now?**

You register datasets under their sources with an expected refresh **cadence**; each
refresh attempt is logged; the app derives a freshness **status** (`fresh` / `stale` /
`failing` / `never`) from the last *successful* refresh versus the cadence, and shows a
dashboard with problems first.

Built for the DataTalksClub **AI Dev Tools Zoomcamp — Homework 1** (spec-driven,
backlog-driven development with an AI coding agent — here, Claude).

> **Scope note:** this is a demo / portfolio build. Refreshes are logged manually
> (UI/admin) or seeded; wiring it to real run metadata (Airflow / dbt / dlt) is an
> explicit v2 item. See `_docs/plan.md` for the freshness rules and their known weak
> points (e.g. a fixed-interval cadence produces false `stale` over weekends).

---

## Homework 1 — answers

| # | Question | Answer |
|---|----------|--------|
| 1 | Coding agent used | **Claude** (Anthropic agent, Cowork / Claude Code) |
| 2 | Features the spec settled on | (1) Dataset catalog · (2) Refresh logging · (3) Freshness status `fresh/stale/failing/never` · (4) Freshness dashboard + history |
| 3 | File to edit to include the app in the project | **`settings.py`** (add `"catalog"` to `INSTALLED_APPS`) |
| 4 | Task 1 in `backlog.md` | **Project & app scaffolding** — create the `config` project and `catalog` app, register it in `INSTALLED_APPS`, wire templates + routing, confirm the server boots |
| 5 | Command to start the dev server | **`uv run python manage.py runserver`** |
| 6 | Command to run the tests | **`python manage.py test`** (with uv: `uv run python manage.py test`) |

Full spec: [`_docs/plan.md`](_docs/plan.md) · Backlog: [`backlog.md`](backlog.md).

---

## Features

1. **Dataset catalog** — datasets under sources, with owner and expected cadence.
2. **Refresh logging** — record each refresh attempt (success / failure).
3. **Freshness status** — `fresh / stale / failing / never`, with optional SLA grace;
   the *latest* failed attempt surfaces as `failing` even over an older success.
4. **Freshness dashboard** — summary counts, problems-first ordering, and a refresh history.

## Stack

Django 5.2 · SQLite · server-rendered templates · `uv` for env/deps. Tests via Django's runner.

---

## Run it — Option A: `uv` (recommended)

Prerequisite: [`uv`](https://docs.astral.sh/uv/) installed. `uv` handles the Python
version and dependencies from `uv.lock`.

```bash
# 1. from the project root
uv sync                                   # create .venv and install deps

# 2. database
uv run python manage.py migrate

# 3. (optional) load demo datasets + refresh logs (fresh/stale/failing/never mix)
uv run python manage.py seed_demo

# 4. (optional) admin user to manage data at /admin/
uv run python manage.py createsuperuser

# 5. run
uv run python manage.py runserver
```

Open <http://127.0.0.1:8000/> — the dashboard is at `/`, refresh history at `/history/`.

## Run it — Option B: Docker Compose

Prerequisite: Docker Desktop (or Docker Engine + Compose). No local Python needed.

```bash
# 1. build the image and start the app (runs migrations, serves on :8000)
docker compose up --build

# 2. (optional, in another terminal) load demo data into the running container
docker compose exec web uv run python manage.py seed_demo

# 3. (optional) create an admin user
docker compose exec web uv run python manage.py createsuperuser
```

Open <http://127.0.0.1:8000/>. Stop with `Ctrl+C`, then `docker compose down`.

> The container's SQLite database is ephemeral (reset when the container is removed) —
> fine for a demo. Mount a volume for `/app/db.sqlite3` to persist it.

---

## Tests

```bash
uv run python manage.py test        # 14 tests
# or, inside Docker:
docker compose run --rm web uv run python manage.py test
```

## Layout

```
config/          Django project (settings, urls)
catalog/         the app: models, views, admin, templates, tests
  management/commands/seed_demo.py   demo data
_docs/plan.md    the specification
backlog.md       the task backlog
Dockerfile       container image (uv-based)
docker-compose.yml
```
