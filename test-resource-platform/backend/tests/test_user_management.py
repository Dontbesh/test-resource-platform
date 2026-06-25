import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_path = tmp_path / "users.db"
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


def login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


def test_admin_can_create_user_and_new_user_can_login(client: TestClient):
    login(client, "admin", "Admin@123456")

    create_response = client.post(
        "/api/v1/users",
        json={"username": "alice", "password": "Alice@123456", "role": "TE"},
    )

    assert create_response.status_code == 201
    assert create_response.json() == {
        "id": 2,
        "username": "alice",
        "role": "TE",
        "is_active": True,
    }

    client.post("/api/v1/auth/logout")
    login(client, "alice", "Alice@123456")
    me_response = client.get("/api/v1/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["username"] == "alice"


def test_non_admin_cannot_access_user_management(client: TestClient):
    login(client, "admin", "Admin@123456")
    client.post(
        "/api/v1/users",
        json={"username": "bob", "password": "Bob@123456", "role": "TE"},
    )
    client.post("/api/v1/auth/logout")
    login(client, "bob", "Bob@123456")

    list_response = client.get("/api/v1/users")
    create_response = client.post(
        "/api/v1/users",
        json={"username": "mallory", "password": "Mallory@123456", "role": "TE"},
    )
    disable_response = client.post("/api/v1/users/1/disable")
    reset_response = client.post(
        "/api/v1/users/1/reset-password",
        json={"password": "Changed@123456"},
    )

    assert list_response.status_code == 403
    assert create_response.status_code == 403
    assert disable_response.status_code == 403
    assert reset_response.status_code == 403
    assert list_response.json()["detail"]["error_code"] == "FORBIDDEN"


def test_admin_can_disable_user_and_existing_session_stops_working(
    client: TestClient,
) -> None:
    login(client, "admin", "Admin@123456")
    create_response = client.post(
        "/api/v1/users",
        json={"username": "carol", "password": "Carol@123456", "role": "TE"},
    )
    user_id = create_response.json()["id"]

    user_client = TestClient(create_app())
    login(user_client, "carol", "Carol@123456")
    assert user_client.get("/api/v1/auth/me").status_code == 200

    disable_response = client.post(f"/api/v1/users/{user_id}/disable")

    assert disable_response.status_code == 200
    assert disable_response.json()["is_active"] is False
    assert user_client.get("/api/v1/auth/me").status_code == 401
    assert (
        user_client.post(
            "/api/v1/auth/login",
            json={"username": "carol", "password": "Carol@123456"},
        ).status_code
        == 401
    )


def test_admin_can_reset_user_password(client: TestClient):
    login(client, "admin", "Admin@123456")
    create_response = client.post(
        "/api/v1/users",
        json={"username": "dave", "password": "Dave@123456", "role": "TSE"},
    )
    user_id = create_response.json()["id"]

    reset_response = client.post(
        f"/api/v1/users/{user_id}/reset-password",
        json={"password": "NewDave@123456"},
    )

    assert reset_response.status_code == 204
    client.post("/api/v1/auth/logout")
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "dave", "password": "Dave@123456"},
        ).status_code
        == 401
    )
    login(client, "dave", "NewDave@123456")


def test_admin_gets_stable_errors_for_duplicate_and_missing_users(client: TestClient):
    login(client, "admin", "Admin@123456")
    client.post(
        "/api/v1/users",
        json={"username": "erin", "password": "Erin@123456", "role": "TE"},
    )

    duplicate_response = client.post(
        "/api/v1/users",
        json={"username": "erin", "password": "Other@123456", "role": "TE"},
    )
    disable_missing_response = client.post("/api/v1/users/999/disable")
    reset_missing_response = client.post(
        "/api/v1/users/999/reset-password",
        json={"password": "Missing@123456"},
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"]["error_code"] == "USERNAME_ALREADY_EXISTS"
    assert disable_missing_response.status_code == 404
    assert disable_missing_response.json()["detail"]["error_code"] == "USER_NOT_FOUND"
    assert reset_missing_response.status_code == 404
    assert reset_missing_response.json()["detail"]["error_code"] == "USER_NOT_FOUND"
