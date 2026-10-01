"""The request metric must carry the route *template* and the status code,
never the raw path (cardinality + privacy)."""

import pytest
from fastapi.testclient import TestClient

from app import main


class Recorder:
    def __init__(self):
        self.calls = []

    def add(self, value, attrs):
        self.calls.append((value, dict(attrs)))

    def record(self, value, attrs):
        self.calls.append((value, dict(attrs)))


@pytest.fixture
def recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "orders.db")
    counter, histogram = Recorder(), Recorder()
    monkeypatch.setattr(main, "REQUESTS", counter)
    monkeypatch.setattr(main, "DURATION", histogram)
    with TestClient(main.app) as client:
        yield client, counter


def test_lookup_metric_has_route_template_and_status(recorded):
    client, counter = recorded
    client.get("/api/orders/standard-1001")
    client.get("/api/orders/does-not-exist")
    attrs = [a for _, a in counter.calls if a["http.route"] == "/api/orders/{order_id}"]
    assert {a["http.response.status_code"] for a in attrs} == {200, 404}
    assert all(a["http.request.method"] == "GET" for a in attrs)
    # no raw ids in metric attributes
    assert not any("standard-1001" in str(a) for _, a in counter.calls)


def test_unhandled_exception_is_counted_as_500(recorded, monkeypatch):
    client, counter = recorded

    def boom(_row):
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "order_detail", boom)
    with TestClient(main.app, raise_server_exceptions=False) as c:
        assert c.get("/api/orders/standard-1001").status_code == 500
    errors = [a for _, a in counter.calls if a["http.response.status_code"] == 500]
    assert errors and errors[-1]["error.type"] == "RuntimeError"
    assert errors[-1]["http.route"] == "/api/orders/{order_id}"
