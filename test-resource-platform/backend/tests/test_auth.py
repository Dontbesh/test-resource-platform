import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_path = tmp_path / "auth.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "Admin@123456")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client


def test_admin_can_login_read_me_and_logout(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )

    assert login_response.status_code == 200
    assert login_response.json() == {
        "id": 1,
        "username": "admin",
        "role": "ADMIN",
        "is_active": True,
    }
    assert "trp_session" in client.cookies

    me_response = client.get("/api/v1/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"

    logout_response = client.post("/api/v1/auth/logout")

    assert logout_response.status_code == 204
    assert "trp_session" not in client.cookies
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"
