import os
import sys
import tempfile
from pathlib import Path

import pytest

# Point the app at a throwaway database and session folder before importing it,
# and force demo mode so tests never call the real market data API.
_tmp = tempfile.mkdtemp(prefix="stocks-tests-")
os.environ["DATABASE_PATH"] = os.path.join(_tmp, "test.db")
os.environ["SESSION_DIR"] = os.path.join(_tmp, "sessions")
os.environ["FINNHUB_API_KEY"] = ""
os.environ["SECRET_KEY"] = "test-secret"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app as flask_app, db  # noqa: E402


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    db.execute("DELETE FROM transactions")
    db.execute("DELETE FROM users")
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", password="secret123"):
    return client.post("/register", data={
        "username": username, "password": password, "confirmation": password})


def login(client, username="alice", password="secret123"):
    return client.post("/login", data={"username": username, "password": password})


@pytest.fixture
def user(client):
    register(client)
    login(client)
    return client
