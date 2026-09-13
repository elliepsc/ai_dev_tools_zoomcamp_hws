"""Unit tests for the pure standings computation."""
from types import SimpleNamespace

from app.standings import compute_standings


def team(id, name):
    return SimpleNamespace(id=id, name=name)


def match(h, a, hs, as_):
    return SimpleNamespace(home_team_id=h, away_team_id=a, home_score=hs, away_score=as_)


def test_empty_league():
    assert compute_standings([], []) == []


def test_win_draw_loss_points():
    teams = [team(1, "A"), team(2, "B"), team(3, "C")]
    matches = [
        match(1, 2, 2, 0),  # A beats B
        match(1, 3, 1, 1),  # A draws C
    ]
    rows = {r["team"]: r for r in compute_standings(teams, matches)}
    assert rows["A"]["points"] == 4  # win + draw
    assert rows["A"]["won"] == 1 and rows["A"]["drawn"] == 1
    assert rows["B"]["points"] == 0 and rows["B"]["lost"] == 1
    assert rows["C"]["points"] == 1 and rows["C"]["drawn"] == 1


def test_goal_stats_and_diff():
    teams = [team(1, "A"), team(2, "B")]
    rows = {r["team"]: r for r in compute_standings(teams, [match(1, 2, 3, 1)])}
    assert rows["A"]["goals_for"] == 3 and rows["A"]["goals_against"] == 1
    assert rows["A"]["goal_diff"] == 2
    assert rows["B"]["goal_diff"] == -2


def test_ranking_orders_by_points_then_goal_diff():
    teams = [team(1, "A"), team(2, "B"), team(3, "C")]
    # A and B both win once; A has a better goal difference.
    matches = [match(1, 3, 5, 0), match(2, 3, 1, 0)]
    order = [r["team"] for r in compute_standings(teams, matches)]
    assert order[0] == "A"  # same points as B, better GD
    assert order[1] == "B"
    assert order[2] == "C"
