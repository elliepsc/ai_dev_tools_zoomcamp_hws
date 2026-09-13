import os
import tempfile

# Point the app at a throwaway SQLite file BEFORE importing it.
_db_path = os.path.join(tempfile.gettempdir(), "scoreboard_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def two_teams(client):
    a = client.post("/api/teams", json={"name": "Lions"}).json()
    b = client.post("/api/teams", json={"name": "Tigers"}).json()
    return a, b
