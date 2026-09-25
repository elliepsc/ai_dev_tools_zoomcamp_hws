"""Read-only post-deploy smoke checks (see conftest.py: this suite runs
against a live, already-deployed instance, never a throwaway one).

test_no_write_verbs_in_smoke_suite is a guard: it fails the whole suite if
any test file under this directory issues a POST/PUT/PATCH/DELETE, so a
future edit here can't silently start writing to a deployed database.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import httpx


def _heading(html: str) -> str:
    match = re.search(r"<h1>(.*?)</h1>", html)
    assert match, "no <h1> heading found"
    return match.group(1)


def test_health(client: httpx.Client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready(client: httpx.Client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_deployed_heading_matches_dashboard_html(client: httpx.Client):
    # tests/smoke/test_smoke.py -> tests/smoke -> tests -> 03-deployment
    dashboard_html_path = Path(__file__).resolve().parents[2] / "dashboard.html"
    expected = _heading(dashboard_html_path.read_text(encoding="utf-8"))
    page = client.get("/")
    assert page.status_code == 200
    assert _heading(page.text) == expected


def test_protected_endpoint_without_token_is_401(client: httpx.Client):
    response = client.get("/api/v1/agents/me")
    assert response.status_code == 401


_WRITE_METHOD_NAMES = {"post", "put", "patch", "delete"}
_WRITE_VERBS = {"POST", "PUT", "PATCH", "DELETE"}


def _write_calls_in(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr = node.func.attr
        if attr in _WRITE_METHOD_NAMES:
            found.append(f"{filename}: .{attr}(...)")
        elif attr == "request" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value.upper() in _WRITE_VERBS:
                found.append(f"{filename}: .request({first.value!r}, ...)")
    return found


def test_no_write_verbs_in_smoke_suite():
    smoke_dir = Path(__file__).resolve().parent
    offenders: list[str] = []
    for py_file in sorted(smoke_dir.glob("*.py")):
        offenders += _write_calls_in(py_file.read_text(encoding="utf-8"), py_file.name)
    assert not offenders, f"tests/smoke must stay read-only, found: {offenders}"
