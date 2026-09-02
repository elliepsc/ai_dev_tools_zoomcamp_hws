# Dataset Freshness Tracker

A small Django app that answers one question a data team asks constantly:
**which of our datasets are stale or failing right now?**

You register datasets under their sources with an expected refresh **cadence**; each
refresh attempt is logged; the app derives a freshness **status** (`fresh` / `stale` /
`failing` / `never`) from the last *successful* refresh versus the cadence, and shows a
dashboard with problems first.

Built for the DataTalksClub **AI Dev Tools Zoomcamp — Homework 1** (spec-driven,
backlog-driven development with an AI coding agent — here, Claude).

> **Scope note:** this is a demo/portfolio build. Refreshes are logged manually (UI/admin)
> or seeded; wiring it to real run metadata (Airflow/dbt/dlt) is an explicit v2 item.

## Features

1. **Dataset catalog** — datasets under sources, with owner and expected cadence.
2. **Refresh logging** — record each refresh attempt (success/failure).
3. **Freshness status** — `fresh / stale / failing / never`, with optional SLA grace.
4. **Freshness dashboard** — summary counts, problems-first ordering, refresh history.

See [`_docs/plan.md`](_docs/plan.md) for the spec (and the freshness rules + their
weak points) and [`backlog.md`](backlog.md) for the task breakdown.

## Stack

Django 5.2 · SQLite · server-rendered templates · `uv`.

## Quickstart

```bash
uv sync                                   # create env + install deps from uv.lock
uv run python manage.py migrate           # apply migrations
uv run python manage.py seed_demo         # optional: demo datasets & refresh logs
uv run python manage.py createsuperuser   # optional: to use /admin/
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/ .

## Tests

```bash
uv run python manage.py test
```

## Layout

```
config/          Django project (settings, urls)
catalog/         the app: models, views, admin, templates, tests
  management/commands/seed_demo.py   demo data
_docs/plan.md    the specification
backlog.md       the task backlog
```
