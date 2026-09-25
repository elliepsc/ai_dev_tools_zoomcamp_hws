"""Fixtures for the read-only post-deploy smoke suite.

This is the only test suite the CI `deploy` job runs against a live,
already-deployed instance (see .github/workflows/hw3-ci.yml at the repo
root). Unlike tests/integration, it must never write anything: a deployed
instance's database is not a throwaway one, and running the full
integration suite there would pollute it with test agents/tasks.

Read-only is enforced twice, independently:
* statically, by test_smoke.py's AST-based guard test (catches an obvious
  ``client.post(...)`` written directly in this directory);
* at runtime, by the ``client`` fixture below: an httpx request event hook
  rejects any method other than GET/HEAD/OPTIONS, which also catches calls
  the AST guard cannot see by construction (e.g. ``client.stream("POST", ...)``,
  or a method name built from a variable).

* ``RELAY_BASE_URL``        base URL of the running API (required; e.g.
                            http://127.0.0.1:18080). If unset, the tests
                            are skipped, so a plain ``pytest`` run of the
                            unit suite still works without a server.
* ``RELAY_REQUIRE_SERVER``  set to 1 in CI: an unset/unreachable server is a
                            failure instead of a silent skip.
"""

from __future__ import annotations

import os

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
        pytest.skip("RELAY_BASE_URL not set: smoke tests need a running Agent Relay")
    return url.rstrip("/")


_ALLOWED_METHODS = {"GET", "HEAD", "OPTIONS"}


def _reject_write_methods(request: httpx.Request) -> None:
    if request.method.upper() not in _ALLOWED_METHODS:
        raise AssertionError(
            f"tests/smoke must stay read-only: attempted {request.method} {request.url}"
        )


@pytest.fixture(scope="session")
def client(base_url: str):
    with httpx.Client(
        base_url=base_url,
        timeout=30,
        event_hooks={"request": [_reject_write_methods]},
    ) as http:
        yield http
