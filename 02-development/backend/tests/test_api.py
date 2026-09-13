"""Integration tests for the API against a real (SQLite) database."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_list_teams(client):
    r = client.post("/api/teams", json={"name": "Lions"})
    assert r.status_code == 201
    assert r.json()["name"] == "Lions"

    teams = client.get("/api/teams").json()
    assert [t["name"] for t in teams] == ["Lions"]


def test_duplicate_team_rejected(client):
    client.post("/api/teams", json={"name": "Lions"})
    r = client.post("/api/teams", json={"name": "Lions"})
    assert r.status_code == 409


def test_create_match_and_standings(client, two_teams):
    lions, tigers = two_teams
    r = client.post(
        "/api/matches",
        json={
            "home_team_id": lions["id"],
            "away_team_id": tigers["id"],
            "home_score": 3,
            "away_score": 1,
        },
    )
    assert r.status_code == 201

    standings = client.get("/api/standings").json()
    top = standings[0]
    assert top["team"] == "Lions"
    assert top["points"] == 3
    assert top["goal_diff"] == 2
    assert standings[1]["team"] == "Tigers"
    assert standings[1]["points"] == 0


def test_match_team_cannot_play_itself(client, two_teams):
    lions, _ = two_teams
    r = client.post(
        "/api/matches",
        json={
            "home_team_id": lions["id"],
            "away_team_id": lions["id"],
            "home_score": 1,
            "away_score": 0,
        },
    )
    assert r.status_code == 400


def test_match_unknown_team_404(client, two_teams):
    lions, _ = two_teams
    r = client.post(
        "/api/matches",
        json={
            "home_team_id": lions["id"],
            "away_team_id": 9999,
            "home_score": 1,
            "away_score": 0,
        },
    )
    assert r.status_code == 404


def test_negative_score_rejected(client, two_teams):
    lions, tigers = two_teams
    r = client.post(
        "/api/matches",
        json={
            "home_team_id": lions["id"],
            "away_team_id": tigers["id"],
            "home_score": -1,
            "away_score": 0,
        },
    )
    assert r.status_code == 422  # pydantic validation (ge=0)
