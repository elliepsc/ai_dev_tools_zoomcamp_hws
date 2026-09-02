# Dataset Freshness Tracker — Specification (plan.md)

## 1. Problem & decision the tool serves

**Vague idea (chosen):** *a lightweight tool to know which of our datasets are stale.*

**Concrete problem:** in a data team, tables and extracts are refreshed on schedules
(hourly/daily/weekly). When a refresh silently stops or fails, dashboards and models
keep serving **stale data** and nobody notices until a stakeholder does. The recurring
question is: *"Right now, which datasets are late or broken, and who owns them?"*

The tool makes **freshness observable**: declare each dataset's expected cadence, log
refresh attempts, and derive a status so the team sees problems first.

## 2. Users & scope

- A single data team (single deployment). No auth/multi-tenant in v1 — it is an internal
  status board, not a SaaS.
- **Out of scope (v1):** automatic ingestion of run metadata from Airflow/dbt/dlt
  (refreshes are logged via the UI/admin or a future API), alerting/notifications,
  per-user permissions, lineage. These are deliberate v2 items.

## 3. Features the spec settles on

1. **Dataset catalog** — register datasets under sources, with owner and expected cadence.
2. **Refresh logging** — record each refresh attempt (success/failure) per dataset.
3. **Freshness status** — derive `fresh / stale / failing / never` from the last
   *successful* refresh vs. cadence (+ optional SLA grace).
4. **Freshness dashboard** — a single board with summary counts and datasets needing
   attention sorted first; plus a refresh history log.

## 4. Data model

- `Source(name, kind[warehouse|api|file|stream], created_at)`
- `Dataset(source → FK, name, owner, description, cadence[hourly|daily|weekly|monthly],
  sla_grace_hours, is_active, created_at)`
- `RefreshLog(dataset → FK, refreshed_at, status[success|failed], row_count, note)`

## 5. Freshness rules (the core logic, and where it can be wrong)

- `due_at = last_success.refreshed_at + cadence + sla_grace`.
- `status()`:
  - no logs → **NEVER**
  - latest attempt failed → **FAILING** (a fresh-but-now-broken table must surface,
    so "latest failed" overrides an older success)
  - `now > due_at` → **STALE**
  - else → **FRESH**

**Observed / interpreted / assumed / uncertain:**
- *Interpreted:* the useful signal is *freshness against an expectation*, not just
  "last updated" — a 3-day-old monthly table is fine; a 2-hour-old hourly table is not.
- *Assumed:* cadence is a fixed interval. Real pipelines have calendars (weekdays only,
  end-of-month) — a naive interval will raise **false STALE** over weekends. Flagged as
  the weakest assumption; v2 would model a schedule/expected-next-run instead of a delta.
- *Assumed:* refreshes are logged truthfully (manual/API). Until run metadata is ingested
  automatically, the board is only as good as what's logged — a real risk to call out.
- *Uncertain:* whether "failing overrides stale" is always the right precedence; some
  teams want to see staleness independently. v1 picks a single status for simplicity.

## 6. Success criteria

- Opening the dashboard answers "what needs attention now?" in one glance, ordered by
  severity, without querying the warehouse manually.

## 7. Tech

Django 5.x · SQLite · server-rendered templates · `uv`. Tests via Django's runner.

> Note: v1 is a **demo/portfolio** build with logged/seeded data, not wired to a live
> warehouse. The value shown is the freshness model and the board, not real ingestion.
