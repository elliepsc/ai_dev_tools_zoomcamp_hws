"""Run SPEC acceptance scenario 1 against a running relay and print a sender
token you can paste into the dashboard.

    uv run python scripts/demo_flow.py --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import time

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--input", default="hello relay")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=30) as http:
        for _ in range(30):  # wait for the server to be ready (DB + schema)
            try:
                if http.get("/ready").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise SystemExit(f"Agent Relay is not ready at {args.base_url}")
        alice = http.post("/api/v1/agents", json={"name": "alice"}).raise_for_status().json()
        bob = http.post("/api/v1/agents", json={"name": "uppercase"}).raise_for_status().json()
        a = {"Authorization": f"Bearer {alice['token']}"}
        b = {"Authorization": f"Bearer {bob['token']}"}

        task = http.post("/api/v1/tasks", headers=a, json={"to": bob["agent_id"], "input": args.input}).json()
        print("sent      ->", task)
        claim = http.post("/api/v1/tasks/claim", headers=b, json={"worker_id": "demo", "wait_seconds": 5}).json()
        print("claimed   -> attempt", claim["attempt"], "status seen by sender:",
              http.get(f"/api/v1/tasks/{task['task_id']}", headers=a).json()["status"])
        done = http.post(
            f"/api/v1/tasks/{task['task_id']}/complete",
            headers=b,
            json={"claim_token": claim["claim_token"], "output": claim["input"].upper()},
        ).json()
        print("completed ->", done)
        final = http.get(f"/api/v1/tasks/{task['task_id']}", headers=a).json()
        print("sender sees:", json.dumps({k: final[k] for k in ("status", "input", "output", "attempt_count")}))
        print("\nPaste this sender token into the dashboard:", alice["token"])


if __name__ == "__main__":
    main()
