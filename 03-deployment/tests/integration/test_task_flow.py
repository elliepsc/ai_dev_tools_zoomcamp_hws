"""SPEC.md acceptance scenario 1 against the real API and database.

Register two agents. One sends a task; the other claims and completes it; the
sender reads the result. Every step goes over HTTP to a running server.
"""

from __future__ import annotations

import os
import uuid

import httpx
from sqlalchemy import create_engine, text


def register(client: httpx.Client, name: str) -> tuple[str, dict[str, str]]:
    response = client.post("/api/v1/agents", json={"name": name, "description": "integration test"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["agent_id"].startswith("agent_")
    assert body["token"].startswith("agt_")
    return body["agent_id"], {"Authorization": f"Bearer {body['token']}"}


def test_health_ready_and_dashboard(client: httpx.Client):
    assert client.get("/health").json() == {"status": "DELIBERATELY-BROKEN-FOR-GATING-PROOF"}
    assert client.get("/ready").json() == {"status": "ready"}
    page = client.get("/")
    assert page.status_code == 200
    assert "<h1>" in page.text
    expected_heading = os.getenv("RELAY_EXPECT_HEADING")
    if expected_heading:
        assert f"<h1>{expected_heading}</h1>" in page.text


def test_two_agents_exchange_task_and_result(client: httpx.Client):
    run = uuid.uuid4().hex[:8]
    sender_id, sender = register(client, f"it-sender-{run}")
    worker_id, worker = register(client, f"it-uppercase-{run}")

    # 1. Sender submits a task to the worker's inbox.
    payload = f"hello relay {run}"
    sent = client.post(
        "/api/v1/tasks",
        headers={**sender, "Idempotency-Key": f"it-{run}"},
        json={"to": worker_id, "input": payload},
    )
    assert sent.status_code == 201, sent.text
    task_id = sent.json()["task_id"]
    assert sent.json()["status"] == "queued"
    assert client.get(f"/api/v1/tasks/{task_id}", headers=sender).json()["status"] == "queued"

    # 2. Worker claims it (long poll). The claim carries a per-attempt token.
    claim = client.post(
        "/api/v1/tasks/claim", headers=worker, json={"worker_id": f"it-{run}", "wait_seconds": 5}
    )
    assert claim.status_code == 200, claim.text
    claimed = claim.json()
    assert claimed["task_id"] == task_id
    assert claimed["from"] == sender_id
    assert claimed["input"] == payload
    assert claimed["attempt"] == 1
    assert claimed["claim_token"].startswith("clm_")
    assert client.get(f"/api/v1/tasks/{task_id}", headers=sender).json()["status"] == "processing"

    # Nothing else is claimable while the lease is active.
    assert client.post(
        "/api/v1/tasks/claim", headers=worker, json={"wait_seconds": 0}
    ).status_code == 204

    # 3. Worker completes it with the deterministic worker's result.
    result = payload.upper()
    done = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=worker,
        json={"claim_token": claimed["claim_token"], "output": result},
    )
    assert done.status_code == 200, done.text
    assert done.json() == {"task_id": task_id, "status": "completed"}

    # A retried identical completion (lost response) is idempotent...
    retry = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=worker,
        json={"claim_token": claimed["claim_token"], "output": result},
    )
    assert retry.status_code == 200
    # ...but a different result for the same claim is rejected.
    conflict = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=worker,
        json={"claim_token": claimed["claim_token"], "output": "something else"},
    )
    assert conflict.status_code == 409

    # 4. Sender reads the result: this is what the dashboard shows.
    task = client.get(f"/api/v1/tasks/{task_id}", headers=sender).json()
    assert task["status"] == "completed"
    assert task["output"] == result
    assert task["error"] is None
    assert task["from"] == sender_id and task["to"] == worker_id
    assert task["attempt_count"] == 1
    assert task["finished_at"] is not None

    attempts = client.get(f"/api/v1/tasks/{task_id}/attempts", headers=sender).json()["items"]
    assert [(a["attempt"], a["outcome"], a["worker_id"]) for a in attempts] == [(1, "completed", f"it-{run}")]

    sent_list = client.get("/api/v1/tasks", params={"direction": "sent"}, headers=sender).json()["items"]
    assert [t["task_id"] for t in sent_list] == [task_id]

    # 5. Access boundary: a third agent cannot read the task.
    _outsider_id, outsider = register(client, f"it-outsider-{run}")
    assert client.get(f"/api/v1/tasks/{task_id}", headers=outsider).status_code == 404

    # 6. Optional: verify the rows really landed in the expected database.
    db_url = os.getenv("RELAY_TEST_DATABASE_URL")
    if not db_url:
        return
    from database import normalize_database_url

    engine = create_engine(normalize_database_url(db_url))
    try:
        expected_dialect = os.getenv("RELAY_EXPECT_DB")
        if expected_dialect:
            assert engine.dialect.name == expected_dialect
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT status, output, sender_id, recipient_id, attempt_count FROM tasks WHERE id = :id"),
                {"id": task_id},
            ).one()
            assert tuple(row) == ("completed", result, sender_id, worker_id, 1)
            outcomes = connection.execute(
                text("SELECT attempt_number, outcome FROM attempts WHERE task_id = :id ORDER BY attempt_number"),
                {"id": task_id},
            ).all()
            assert [tuple(o) for o in outcomes] == [(1, "completed")]
            # Tokens are stored hashed, never in clear text.
            token_hash = connection.execute(
                text("SELECT token_hash FROM agents WHERE id = :id"), {"id": sender_id}
            ).scalar_one()
            assert len(token_hash) == 64 and not token_hash.startswith("agt_")
    finally:
        engine.dispose()


def test_unauthenticated_calls_are_rejected(client: httpx.Client):
    assert client.get("/api/v1/tasks", params={"direction": "sent"}).status_code == 401
    bad = client.get("/api/v1/agents/me", headers={"Authorization": "Bearer agt_not-a-real-token"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"


def test_empty_inbox_returns_204(client: httpx.Client):
    _agent_id, headers = register(client, f"it-idle-{uuid.uuid4().hex[:8]}")
    response = client.post("/api/v1/tasks/claim", headers=headers, json={"wait_seconds": 0})
    assert response.status_code == 204


def test_shipped_worker_process_completes_task(client: httpx.Client, base_url: str):
    """Same scenario, but the recipient is the real `python main.py worker` process."""

    import subprocess
    import sys
    import time
    from pathlib import Path

    run = uuid.uuid4().hex[:8]
    _sender_id, sender = register(client, f"it-sender-{run}")
    response = client.post("/api/v1/agents", json={"name": f"it-worker-{run}"})
    worker = response.json()
    task_id = client.post(
        "/api/v1/tasks", headers=sender, json={"to": worker["agent_id"], "input": f"from worker {run}"}
    ).json()["task_id"]

    repo_root = Path(__file__).resolve().parents[2]
    process = subprocess.run(
        [
            sys.executable, "main.py", "worker",
            "--base-url", base_url,
            "--agent-id", worker["agent_id"],
            "--token", worker["token"],
            "--worker-id", f"proc-{run}",
            "--wait-seconds", "5",
            "--stop-after", "1",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stderr

    deadline = time.monotonic() + 10
    while True:
        task = client.get(f"/api/v1/tasks/{task_id}", headers=sender).json()
        if task["status"] == "completed" or time.monotonic() > deadline:
            break
        time.sleep(0.2)
    assert task["status"] == "completed"
    assert task["output"] == f"from worker {run}".upper()
