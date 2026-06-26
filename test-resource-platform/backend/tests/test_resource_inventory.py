import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_path = tmp_path / "resources.db"
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


def create_user(client: TestClient, username: str, password: str, role: str) -> None:
    response = client.post(
        "/api/v1/users",
        json={"username": username, "password": password, "role": role},
    )
    assert response.status_code == 201


def test_admin_can_create_resource_pool_and_machine_then_te_can_list(
    client: TestClient,
) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te01", "Te01@123456", "TE")

    pool_response = client.post(
        "/api/v1/resource-pools",
        json={
            "name": "lab-a",
            "description": "Main lab pool",
            "network_zone": "intranet-a",
        },
    )
    assert pool_response.status_code == 201
    pool = pool_response.json()
    assert pool["name"] == "lab-a"

    machine_response = client.post(
        "/api/v1/machines",
        json={
            "resource_code": "SN-PHY-001",
            "name": "phy-001",
            "resource_type": "PHYSICAL",
            "pool_id": pool["id"],
            "architecture": "x86_64",
            "os_name": "Ubuntu 22.04",
            "ip_address": "192.168.10.11",
            "tags": ["smoke", "linux"],
        },
    )
    assert machine_response.status_code == 201
    machine = machine_response.json()
    assert machine["resource_code"] == "SN-PHY-001"
    assert machine["admin_status"] == "ACTIVE"
    assert machine["connectivity_status"] == "UNKNOWN"

    client.post("/api/v1/auth/logout")
    login(client, "te01", "Te01@123456")

    pools_response = client.get("/api/v1/resource-pools")
    machines_response = client.get("/api/v1/machines")

    assert pools_response.status_code == 200
    assert pools_response.json()[0]["name"] == "lab-a"
    assert machines_response.status_code == 200
    assert machines_response.json()[0]["resource_code"] == "SN-PHY-001"


def test_tse_can_create_inventory_but_te_cannot(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "tse01", "Tse01@123456", "TSE")
    create_user(client, "te02", "Te02@123456", "TE")
    client.post("/api/v1/auth/logout")

    login(client, "tse01", "Tse01@123456")
    pool_response = client.post(
        "/api/v1/resource-pools",
        json={"name": "lab-b", "description": "Secondary lab"},
    )
    assert pool_response.status_code == 201
    pool_id = pool_response.json()["id"]

    machine_response = client.post(
        "/api/v1/machines",
        json={
            "resource_code": "VM-UUID-001",
            "name": "vm-001",
            "resource_type": "VIRTUAL",
            "pool_id": pool_id,
        },
    )
    assert machine_response.status_code == 201
    client.post("/api/v1/auth/logout")

    login(client, "te02", "Te02@123456")
    forbidden_pool_response = client.post(
        "/api/v1/resource-pools",
        json={"name": "lab-c"},
    )
    forbidden_machine_response = client.post(
        "/api/v1/machines",
        json={
            "resource_code": "SN-PHY-002",
            "name": "phy-002",
            "resource_type": "PHYSICAL",
            "pool_id": pool_id,
        },
    )

    assert forbidden_pool_response.status_code == 403
    assert forbidden_machine_response.status_code == 403


def test_inventory_returns_stable_conflict_and_missing_pool_errors(
    client: TestClient,
) -> None:
    login(client, "admin", "Admin@123456")
    pool_response = client.post(
        "/api/v1/resource-pools",
        json={"name": "lab-d"},
    )
    pool_id = pool_response.json()["id"]
    client.post(
        "/api/v1/machines",
        json={
            "resource_code": "SN-PHY-003",
            "name": "phy-003",
            "resource_type": "PHYSICAL",
            "pool_id": pool_id,
        },
    )

    duplicate_pool_response = client.post(
        "/api/v1/resource-pools",
        json={"name": "lab-d"},
    )
    duplicate_machine_response = client.post(
        "/api/v1/machines",
        json={
            "resource_code": "SN-PHY-003",
            "name": "phy-003-copy",
            "resource_type": "PHYSICAL",
            "pool_id": pool_id,
        },
    )
    missing_pool_response = client.post(
        "/api/v1/machines",
        json={
            "resource_code": "SN-PHY-004",
            "name": "phy-004",
            "resource_type": "PHYSICAL",
            "pool_id": 999,
        },
    )

    assert duplicate_pool_response.status_code == 409
    assert (
        duplicate_pool_response.json()["detail"]["error_code"]
        == "RESOURCE_POOL_NAME_ALREADY_EXISTS"
    )
    assert duplicate_machine_response.status_code == 409
    assert (
        duplicate_machine_response.json()["detail"]["error_code"]
        == "RESOURCE_CODE_ALREADY_EXISTS"
    )
    assert missing_pool_response.status_code == 404
    assert missing_pool_response.json()["detail"]["error_code"] == "RESOURCE_POOL_NOT_FOUND"
