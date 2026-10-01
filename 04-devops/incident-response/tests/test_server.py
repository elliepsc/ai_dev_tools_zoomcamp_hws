import json

import pytest
from fastapi.testclient import TestClient

from responder import server
from responder.pipeline import Responder, Settings

TEST_ALERT = {"alerts": [{"status": "firing", "labels": {"alertname": "ResponderTest", "test": "true"},
                          "annotations": {"summary": "Test notification; no incident to fix"}}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RESPONDER_INCIDENTS_DIR", str(tmp_path / "incidents"))
    monkeypatch.setenv("RESPONDER_TOKEN", "s3cret")
    server._responder = Responder(Settings())
    while not server._jobs.empty():
        server._jobs.get_nowait()
    return TestClient(server.app, client=("10.215.24.5", 5000))


def test_non_loopback_needs_token(client):
    assert client.post("/alerts", json=TEST_ALERT).status_code == 401
    assert client.post("/alerts", json=TEST_ALERT, headers={"Authorization": "Bearer nope"}).status_code == 401
    r = client.post("/alerts", json=TEST_ALERT, headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 202
    assert r.json()["accepted"][0]["status"] == "queued"


def test_same_alert_is_deduplicated(client):
    h = {"Authorization": "Bearer s3cret"}
    first = client.post("/alerts", json=TEST_ALERT, headers=h).json()["accepted"][0]
    second = client.post("/alerts", json=TEST_ALERT, headers=h).json()["accepted"][0]
    assert second["incident"] == first["incident"]
    assert second["status"] == "attached_to_open_incident"
    assert server._jobs.qsize() == 1


def test_rejects_garbage(client):
    h = {"Authorization": "Bearer s3cret"}
    assert client.post("/alerts", content=b"not json", headers={**h, "Content-Type": "application/json"}).status_code == 400
    assert client.post("/alerts", json={"alerts": []}, headers=h).status_code == 422
    assert client.get("/incidents/../../etc/passwd", headers=h).status_code == 404


def test_browser_csrf_and_read_endpoints_are_guarded(client):
    h = {"Authorization": "Bearer s3cret"}
    # text/plain "simple request" (what a malicious web page could send without preflight)
    assert client.post("/alerts", content=b'{"alerts":[{}]}', headers={**h, "Content-Type": "text/plain"}).status_code == 415
    assert client.post("/alerts", json=TEST_ALERT, headers={**h, "Origin": "https://evil.example"}).status_code == 403
    assert client.get("/incidents").status_code == 401
    assert client.get("/incidents", headers=h).status_code == 200


def test_alert_is_stored_redacted(client, tmp_path):
    alert = {"alerts": [{"status": "firing", "labels": {"alertname": "X"},
                         "annotations": {"summary": "token=abcd1234 leaked by bob@example.com"}}]}
    inc = client.post("/alerts", json=alert, headers={"Authorization": "Bearer s3cret"}).json()["accepted"][0]["incident"]
    stored = (tmp_path / "incidents" / inc / "alert.json").read_text()
    assert "abcd1234" not in stored and "bob@example.com" not in stored


def test_human_can_close_an_incident_so_the_next_alert_opens_a_new_one(client):
    h = {"Authorization": "Bearer s3cret"}
    first = client.post("/alerts", json=TEST_ALERT, headers=h).json()["accepted"][0]["incident"]
    r = client.post(f"/incidents/{first}/close", json={"disposition": "test only", "by": "ellie"}, headers=h)
    assert r.status_code == 200 and r.json()["state"] == "closed"
    second = client.post("/alerts", json=TEST_ALERT, headers=h).json()["accepted"][0]
    assert second["incident"] != first and second["status"] == "queued"
