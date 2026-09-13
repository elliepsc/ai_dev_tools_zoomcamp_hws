# TopTable — Specification

## 1. Idea

**TopTable** is a small sports-league scoreboard: register teams, record match
results, and see an automatically computed league table. Chosen from the Homework 2
project options (sports-league scoreboard).

## 2. Users & scope

- One league per deployment; no authentication (internal/demo tool).
- **In scope (v1):** teams, match results, computed standings.
- **Out of scope (v1):** fixtures/scheduling, multiple leagues, editing/deleting
  results, auth. Deliberate v2 items.

## 3. Features

1. **Teams** — add a team (unique name), list teams.
2. **Matches** — record a result (home team, away team, scores).
3. **Standings** — a league table computed from results: played, W/D/L, goals for/against,
   goal difference, points.

## 4. Data model

- `Team(id, name unique)`
- `Match(id, home_team_id, away_team_id, home_score, away_score, round)`

Standings are **derived**, never stored — they are recomputed from matches so they can
never drift from the results.

## 5. Rules

- Points: win = 3, draw = 1, loss = 0.
- Ranking: points, then goal difference, then goals scored, then name (A→Z) as a stable
  tie-break.
- A team cannot play itself; both teams must exist; scores are ≥ 0 (validated).

## 6. Architecture

- **Backend:** FastAPI (Python, `uv`), SQLAlchemy 2.0, database-agnostic via
  `DATABASE_URL` (SQLite by default). OpenAPI contract auto-generated (`/openapi.json`,
  exported to `openapi.yaml`).
- **Frontend:** React + Vite. All backend calls centralized in `src/api.js`; base URL
  configurable via `VITE_API_URL` (defaults to `http://localhost:8000`).
- **Tests:** pytest — pure standings logic + API integration against a real SQLite DB.

## 7. Success criteria

Add teams, record results, and the table updates correctly and consistently, with the
standings always reflecting the recorded matches.
