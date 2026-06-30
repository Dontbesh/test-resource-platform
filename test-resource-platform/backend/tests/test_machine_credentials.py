import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.credentials.models import CredentialAccessEvent, MachineCredential
from app.db.session import get_engine, get_session_factory
from app.main import create_app

TEST_FERNET_KEY = "P4hnnBWP4qB-txrlIG20aQRk0RxEholITHKAcC3atkY="


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_path = tmp_path / "credentials.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", TEST_FERNET_KEY)
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


def create_machine(
    client: TestClient,
    resource_code: str = "SN-CRED-001",
    is_critical: bool = False,
) -> None:
    pool_response = client.post(
        "/api/v1/resource-pools",
        json={"name": f"pool-{resource_code.lower()}"},
    )
    assert pool_response.status_code == 201
    machine_response = client.post(
        "/api/v1/machines",
        json={
            "resource_code": resource_code,
            "name": resource_code.lower(),
            "resource_type": "PHYSICAL",
            "pool_id": pool_response.json()["id"],
            "is_critical": is_critical,
            "ip_address": "192.0.2.10",
            "bmc_address": "192.0.2.20",
        },
    )
    assert machine_response.status_code == 201


def configure_credentials(client: TestClient, resource_code: str = "SN-CRED-001") -> dict:
    response = client.put(
        f"/api/v1/machines/{resource_code}/credentials",
        json={
            "ssh_username": "root",
            "ssh_password": "ssh-secret",
            "bmc_username": "Administrator",
            "bmc_password": "bmc-secret",
        },
    )
    assert response.status_code == 200
    return response.json()


def lease_machine(client: TestClient, resource_code: str = "SN-CRED-001") -> str:
    response = client.post(
        "/api/v1/leases",
        json={
            "resource_code": resource_code,
            "duration_minutes": 60,
            "purpose": "credential test",
        },
    )
    assert response.status_code == 201
    return response.json()["lease_id"]


def test_admin_or_tse_can_configure_credentials_without_password_echo(
    client: TestClient,
) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "tse-cred", "TseCred@123456", "TSE")
    create_machine(client)
    client.post("/api/v1/auth/logout")
    login(client, "tse-cred", "TseCred@123456")

    body = configure_credentials(client)

    assert body == {
        "resource_code": "SN-CRED-001",
        "ssh_username": "root",
        "has_ssh_password": True,
        "bmc_username": "Administrator",
        "has_bmc_password": True,
    }


def test_credentials_are_not_stored_as_plaintext(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_machine(client)
    configure_credentials(client)

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        credential = session.scalar(select(MachineCredential))
        assert credential is not None
        assert credential.encrypted_ssh_password != "ssh-secret"
        assert credential.encrypted_bmc_password != "bmc-secret"
        assert "ssh-secret" not in credential.encrypted_ssh_password
        assert "bmc-secret" not in credential.encrypted_bmc_password


def test_current_lease_owner_can_view_plain_credentials_and_creates_audit_event(
    client: TestClient,
) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-owner", "TeOwner@123456", "TE")
    create_machine(client)
    configure_credentials(client)
    client.post("/api/v1/auth/logout")
    login(client, "te-owner", "TeOwner@123456")
    lease_machine(client)

    response = client.get("/api/v1/machines/SN-CRED-001/credentials")

    assert response.status_code == 200
    assert response.json()["ssh_password"] == "ssh-secret"
    assert response.json()["bmc_password"] == "bmc-secret"
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        event = session.scalar(select(CredentialAccessEvent))
        assert event is not None
        assert event.access_type == "VIEW"


def test_non_owner_cannot_view_plain_credentials(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-owner2", "TeOwner2@123456", "TE")
    create_user(client, "te-other", "TeOther@123456", "TE")
    create_machine(client)
    configure_credentials(client)
    client.post("/api/v1/auth/logout")
    login(client, "te-owner2", "TeOwner2@123456")
    lease_machine(client)
    client.post("/api/v1/auth/logout")
    login(client, "te-other", "TeOther@123456")

    response = client.get("/api/v1/machines/SN-CRED-001/credentials")

    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "CREDENTIAL_NOT_VISIBLE"


def test_critical_machine_credentials_are_admin_only(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-critical", "TeCritical@123456", "TE")
    create_machine(client, "SN-CRED-CRITICAL", is_critical=True)
    configure_credentials(client, "SN-CRED-CRITICAL")
    client.post("/api/v1/auth/logout")
    login(client, "te-critical", "TeCritical@123456")
    lease_machine(client, "SN-CRED-CRITICAL")

    forbidden_response = client.get("/api/v1/machines/SN-CRED-CRITICAL/credentials")
    client.post("/api/v1/auth/logout")
    login(client, "admin", "Admin@123456")
    admin_response = client.get("/api/v1/machines/SN-CRED-CRITICAL/credentials")

    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"]["error_code"] == "CREDENTIAL_NOT_VISIBLE"
    assert admin_response.status_code == 200
    assert admin_response.json()["ssh_password"] == "ssh-secret"
