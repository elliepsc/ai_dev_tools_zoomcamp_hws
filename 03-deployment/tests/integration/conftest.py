"""Fixtures for the black-box integration tests.

These tests talk to a *running* Agent Relay over real HTTP (uvicorn, Docker,
Compose or Kubernetes) and, optionally, read the database it writes to.

* ``RELAY_BASE_URL``        base URL of the running API (required; e.g.
                            http://127.0.0.1:8000). If unset the tests are
                            skipped, so a plain ``pytest`` run of the unit
                            suite still works without a server.
* ``RELAY_REQUIRE_SERVER``  set to 1 in CI: an unset/unreachable server is a
                            failure instead of a skip (a pipeline that
                            silently skips its integration tests is worse
                            than no pipeline).
* ``RELAY_TEST_DATABASE_URL``  optional; if set, the test also checks the rows
                            in that database (proves which DB the API uses).
* ``RELAY_EXPECT_DB``       optional ``postgresql`` / ``sqlite``: assert the
                            backend dialect of RELAY_TEST_DATABASE_URL.

The tests never drop or truncate tables: they create uniquely named agents so
they are safe to run against a shared dev database.
"""

from __future__ import annotations

import os
import time

import httpx
import pytest


def _require_server() -> bool:
    return os.getenv("RELAY_REQUIRE_SERVER", "").lower() in {"1", "true", "yes"}


@pytest.fixture(scope="session")
def base_url() -> str:
    url = os.getenv("RELAY_BASE_URL")
    if not url:
        if _require_server():
            pytest.fail("RELAY_BASE_URL is not set but RELAY_REQUIRE_SERVER=1")
        pytest.skip("RELAY_BASE_URL not set: integration tests need a running Agent Relay")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def client(base_url: str):
    with httpx.Client(base_url=base_url, timeout=30) as http:
        deadline = time.monotonic() + float(os.getenv("RELAY_WAIT_READY_SECONDS", "30"))
        last_error = "no response"
        while time.monotonic() < deadline:
            try:
                response = http.get("/ready")
                if response.status_code == 200:
                    break
                last_error = f"/ready returned {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = repr(exc)
            time.sleep(1)
        else:
            message = f"Agent Relay at {base_url} is not ready: {last_error}"
            if _require_server():
                pytest.fail(message)
            pytest.skip(message)
        yield http
