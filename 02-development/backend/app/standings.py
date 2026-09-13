"""Pure standings computation — no database, so it is trivial to unit-test.

Points: win = 3, draw = 1, loss = 0. Ranking: points, then goal difference,
then goals scored, then name (alphabetical) as a stable tie-break.
"""
from __future__ import annotations

WIN_POINTS = 3
DRAW_POINTS = 1


def compute_standings(teams, matches):
    table = {
        t.id: {
            "team_id": t.id,
            "team": t.name,
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_diff": 0,
            "points": 0,
        }
        for t in teams
    }

    for m in matches:
        home = table.get(m.home_team_id)
        away = table.get(m.away_team_id)
        if home is None or away is None:
            continue  # match references a deleted team; skip defensively

        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += m.home_score
        home["goals_against"] += m.away_score
        away["goals_for"] += m.away_score
        away["goals_against"] += m.home_score

        if m.home_score > m.away_score:
            home["won"] += 1
            home["points"] += WIN_POINTS
            away["lost"] += 1
        elif m.home_score < m.away_score:
            away["won"] += 1
            away["points"] += WIN_POINTS
            home["lost"] += 1
        else:
            home["drawn"] += 1
            away["drawn"] += 1
            home["points"] += DRAW_POINTS
            away["points"] += DRAW_POINTS

    for row in table.values():
        row["goal_diff"] = row["goals_for"] - row["goals_against"]

    return sorted(
        table.values(),
        key=lambda r: (-r["points"], -r["goal_diff"], -r["goals_for"], r["team"].lower()),
    )
