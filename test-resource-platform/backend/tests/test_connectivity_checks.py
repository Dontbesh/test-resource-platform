import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_path = tmp_path / "connectivity.db"
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


class FakeConnectivityChecker:
    def check(self, host: str, port: int, timeout_seconds: float):
        if port == 22:
            return True, 12, None
        return False, 15, "connection refused"


def login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


def create_machine(client: TestClient) -> None:
    pool_response = client.post(
        "/api/v1/resource-pools",
        json={"name": "connectivity-pool"},
    )
    assert pool_response.status_code == 201
    machine_response = client.post(
        "/api/v1/machines",
        json={
            "resource_code": "SN-CONN-001",
            "name": "conn-001",
            "resource_type": "PHYSICAL",
            "pool_id": pool_response.json()["id"],
            "ip_address": "192.0.2.10",
            "bmc_address": "192.0.2.20",
        },
    )
    assert machine_response.status_code == 201


def test_connectivity_check_returns_per_target_status(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.connectivity_checks.get_connectivity_checker",
        lambda: FakeConnectivityChecker(),
    )
    login(client, "admin", "Admin@123456")
    create_machine(client)

    response = client.post("/api/v1/machines/SN-CONN-001/connectivity-checks")

    assert response.status_code == 200
    assert response.json() == {
        "resource_code": "SN-CONN-001",
        "checks": [
            {
                "target": "SSH",
                "host": "192.0.2.10",
                "port": 22,
                "status": "REACHABLE",
                "latency_ms": 12,
                "error": None,
            },
            {
                "target": "BMC_HTTPS",
                "host": "192.0.2.20",
                "port": 443,
                "status": "UNREACHABLE",
                "latency_ms": 15,
                "error": "connection refused",
            },
        ],
    }
