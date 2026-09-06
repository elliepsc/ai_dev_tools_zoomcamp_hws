# Backlog — Dataset Freshness Tracker (Django)

Ordered, atomic tasks. Each is independently testable.

## Task 1 — Project & app scaffolding
Set up the Django project (`config`) and the `catalog` app, register the app in
`INSTALLED_APPS` (`config/settings.py`), configure the templates dir and base URL
routing, and confirm the dev server boots (`uv run python manage.py runserver`).
- **Done when:** `manage.py check` passes and `/` returns a page.
- **Depends on:** none.

## Task 2 — Data model & migrations
Implement `Source`, `Dataset`, `RefreshLog` per `_docs/plan.md` (section 4), register
them in the admin, and create/apply migrations.
- **Done when:** migrations apply; objects creatable via admin/shell.
- **Depends on:** Task 1.

## Task 3 — Freshness logic
Add `Dataset.due_at()` and `Dataset.status()` implementing the rules in plan.md
section 5 (never/fresh/stale/failing, latest-failure precedence, SLA grace).
- **Done when:** unit tests prove each status branch, incl. grace and failure precedence.
- **Depends on:** Task 2.

## Task 4 — Freshness dashboard + refresh action
A board listing active datasets with source, owner, cadence, hours-since-success and a
status badge, summary counts, problems-first ordering, and POST actions to log a
success/failed refresh.
- **Done when:** actions log a `RefreshLog` and the status updates; summary counts match.
- **Depends on:** Task 3.

## Task 5 — Refresh history
Chronological list of the last refresh attempts (when / dataset / source / outcome).
- **Done when:** attempts appear newest-first with correct outcome.
- **Depends on:** Task 4.

## Task 6 — Tests & seed data
Cover status logic and views with Django tests; add a `seed_demo` command producing a
realistic fresh/stale/failing/never mix.
- **Done when:** `python manage.py test` is green and the seeded board renders.
- **Depends on:** Tasks 3–5.
