import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_fd, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-bytes-long-for-hs256"
os.environ["SEED_USER_EMAIL"] = "test@example.com"
os.environ["SEED_USER_PASSWORD"] = "testpass123"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import SessionLocal, seed_default_user
from db import Base, engine


@pytest.fixture
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_default_user(db)
    finally:
        db.close()
    yield


@pytest.fixture
def client(reset_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    resp = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
