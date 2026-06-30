from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.leases.models import LeaseEventType, ResourceLease, ResourceLeaseEvent
from app.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_path = tmp_path / "leases.db"
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


def create_pool_and_machine(client: TestClient, resource_code: str = "SN-PHY-LEASE-001") -> int:
    pool_response = client.post(
        "/api/v1/resource-pools",
        json={"name": f"pool-{resource_code.lower()}"},
    )
    assert pool_response.status_code == 201
    pool_id = pool_response.json()["id"]
    machine_response = client.post(
        "/api/v1/machines",
        json={
            "resource_code": resource_code,
            "name": resource_code.lower(),
            "resource_type": "PHYSICAL",
            "pool_id": pool_id,
        },
    )
    assert machine_response.status_code == 201
    return pool_id


def create_lease(
    client: TestClient,
    resource_code: str = "SN-PHY-LEASE-001",
    duration_minutes: int = 60,
) -> dict:
    response = client.post(
        "/api/v1/leases",
        json={
            "resource_code": resource_code,
            "duration_minutes": duration_minutes,
            "purpose": "smoke test",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_logged_in_user_can_lease_available_machine(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-lease", "TeLease@123456", "TE")
    create_pool_and_machine(client)
    client.post("/api/v1/auth/logout")
    login(client, "te-lease", "TeLease@123456")

    lease_response = client.post(
        "/api/v1/leases",
        json={
            "resource_code": "SN-PHY-LEASE-001",
            "duration_minutes": 60,
            "purpose": "smoke test",
        },
    )

    assert lease_response.status_code == 201
    lease = lease_response.json()
    assert lease["lease_id"]
    assert lease["status"] == "ACTIVE"
    assert lease["machine"]["resource_code"] == "SN-PHY-LEASE-001"
    assert lease["user"]["username"] == "te-lease"
    assert lease["purpose"] == "smoke test"

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        event = session.scalar(
            select(ResourceLeaseEvent).where(ResourceLeaseEvent.lease_id == lease["lease_id"])
        )
        assert event is not None
        assert event.event_type == LeaseEventType.CREATED
        assert event.target_user.username == "te-lease"


def test_active_lease_blocks_second_lease_for_same_machine(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-first", "TeFirst@123456", "TE")
    create_user(client, "te-second", "TeSecond@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-002")
    client.post("/api/v1/auth/logout")

    login(client, "te-first", "TeFirst@123456")
    create_lease(client, "SN-PHY-LEASE-002")
    client.post("/api/v1/auth/logout")
    login(client, "te-second", "TeSecond@123456")

    conflict_response = client.post(
        "/api/v1/leases",
        json={
            "resource_code": "SN-PHY-LEASE-002",
            "duration_minutes": 60,
            "purpose": "second user",
        },
    )

    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"]["error_code"] == "RESOURCE_ALREADY_LEASED"


def test_machine_list_shows_occupancy_status_and_lease_user(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-occupant", "TeOccupant@123456", "TE")
    create_user(client, "te-viewer", "TeViewer@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-008")
    create_pool_and_machine(client, "SN-PHY-LEASE-009")
    client.post("/api/v1/auth/logout")
    login(client, "te-occupant", "TeOccupant@123456")
    create_lease(client, "SN-PHY-LEASE-008")
    client.post("/api/v1/auth/logout")
    login(client, "te-viewer", "TeViewer@123456")

    machines_response = client.get("/api/v1/machines")

    assert machines_response.status_code == 200
    machines = {machine["resource_code"]: machine for machine in machines_response.json()}
    assert machines["SN-PHY-LEASE-008"]["occupancy_status"] == "OCCUPIED"
    assert machines["SN-PHY-LEASE-008"]["leased_by_username"] == "te-occupant"
    assert machines["SN-PHY-LEASE-009"]["occupancy_status"] == "FREE"
    assert machines["SN-PHY-LEASE-009"]["leased_by_username"] is None


def test_disabled_pool_or_machine_cannot_be_leased(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-disabled", "TeDisabled@123456", "TE")
    disabled_pool_id = create_pool_and_machine(client, "SN-PHY-LEASE-003")
    create_pool_and_machine(client, "SN-PHY-LEASE-004")
    client.post(f"/api/v1/resource-pools/{disabled_pool_id}/disable")
    client.post("/api/v1/machines/SN-PHY-LEASE-004/disable")
    client.post("/api/v1/auth/logout")
    login(client, "te-disabled", "TeDisabled@123456")

    disabled_pool_response = client.post(
        "/api/v1/leases",
        json={
            "resource_code": "SN-PHY-LEASE-003",
            "duration_minutes": 60,
            "purpose": "disabled pool",
        },
    )
    disabled_machine_response = client.post(
        "/api/v1/leases",
        json={
            "resource_code": "SN-PHY-LEASE-004",
            "duration_minutes": 60,
            "purpose": "disabled machine",
        },
    )

    assert disabled_pool_response.status_code == 409
    assert disabled_pool_response.json()["detail"]["error_code"] == "RESOURCE_POOL_DISABLED"
    assert disabled_machine_response.status_code == 409
    assert disabled_machine_response.json()["detail"]["error_code"] == "MACHINE_NOT_AVAILABLE"


def test_user_can_list_and_release_own_active_lease(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-owner", "TeOwner@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-005")
    client.post("/api/v1/auth/logout")
    login(client, "te-owner", "TeOwner@123456")
    lease = create_lease(client, "SN-PHY-LEASE-005")

    list_response = client.get("/api/v1/leases/my")
    release_response = client.post(f"/api/v1/leases/{lease['lease_id']}/release")
    second_lease_response = client.post(
        "/api/v1/leases",
        json={
            "resource_code": "SN-PHY-LEASE-005",
            "duration_minutes": 60,
            "purpose": "after release",
        },
    )

    assert list_response.status_code == 200
    assert [item["lease_id"] for item in list_response.json()] == [lease["lease_id"]]
    assert release_response.status_code == 200
    assert release_response.json()["status"] == "RELEASED"
    assert release_response.json()["released_at"] is not None
    assert second_lease_response.status_code == 201

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        events = list(
            session.scalars(
                select(ResourceLeaseEvent)
                .where(ResourceLeaseEvent.lease_id == lease["lease_id"])
                .order_by(ResourceLeaseEvent.id)
            )
        )
        assert [event.event_type for event in events] == [
            LeaseEventType.CREATED,
            LeaseEventType.RELEASED,
        ]


def test_user_can_extend_own_active_lease_and_creates_event(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-extend", "TeExtend@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-010")
    client.post("/api/v1/auth/logout")
    login(client, "te-extend", "TeExtend@123456")
    lease = create_lease(client, "SN-PHY-LEASE-010", duration_minutes=60)
    original_expires_at = datetime.fromisoformat(lease["expires_at"])

    extend_response = client.post(
        f"/api/v1/leases/{lease['lease_id']}/extend",
        json={"duration_minutes": 30},
    )

    assert extend_response.status_code == 200
    extended_lease = extend_response.json()
    assert extended_lease["lease_id"] == lease["lease_id"]
    assert datetime.fromisoformat(extended_lease["expires_at"]) == original_expires_at + timedelta(
        minutes=30
    )

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        events = list(
            session.scalars(
                select(ResourceLeaseEvent)
                .where(ResourceLeaseEvent.lease_id == lease["lease_id"])
                .order_by(ResourceLeaseEvent.id)
            )
        )
        assert [event.event_type for event in events] == [
            LeaseEventType.CREATED,
            LeaseEventType.EXTENDED,
        ]
        assert events[-1].previous_expires_at is not None
        assert events[-1].new_expires_at is not None


def test_user_cannot_extend_another_users_lease(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-extend-owner", "TeExtendOwner@123456", "TE")
    create_user(client, "te-extend-other", "TeExtendOther@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-011")
    client.post("/api/v1/auth/logout")
    login(client, "te-extend-owner", "TeExtendOwner@123456")
    lease = create_lease(client, "SN-PHY-LEASE-011")
    client.post("/api/v1/auth/logout")
    login(client, "te-extend-other", "TeExtendOther@123456")

    extend_response = client.post(
        f"/api/v1/leases/{lease['lease_id']}/extend",
        json={"duration_minutes": 30},
    )

    assert extend_response.status_code == 403
    assert extend_response.json()["detail"]["error_code"] == "LEASE_NOT_OWNED"


def test_released_or_expired_lease_cannot_be_extended(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-extend-state", "TeExtendState@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-012")
    create_pool_and_machine(client, "SN-PHY-LEASE-013")
    client.post("/api/v1/auth/logout")
    login(client, "te-extend-state", "TeExtendState@123456")
    released_lease = create_lease(client, "SN-PHY-LEASE-012")
    expired_lease = create_lease(client, "SN-PHY-LEASE-013")
    client.post(f"/api/v1/leases/{released_lease['lease_id']}/release")

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        lease = session.scalar(
            select(ResourceLease).where(ResourceLease.lease_id == expired_lease["lease_id"])
        )
        assert lease is not None
        lease.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    released_extend_response = client.post(
        f"/api/v1/leases/{released_lease['lease_id']}/extend",
        json={"duration_minutes": 30},
    )
    expired_extend_response = client.post(
        f"/api/v1/leases/{expired_lease['lease_id']}/extend",
        json={"duration_minutes": 30},
    )

    assert released_extend_response.status_code == 409
    assert released_extend_response.json()["detail"]["error_code"] == "LEASE_NOT_ACTIVE"
    assert expired_extend_response.status_code == 409
    assert expired_extend_response.json()["detail"]["error_code"] == "LEASE_NOT_ACTIVE"


def test_admin_can_force_release_another_users_active_lease_and_creates_event(
    client: TestClient,
) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-force-owner", "TeForceOwner@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-014")
    client.post("/api/v1/auth/logout")
    login(client, "te-force-owner", "TeForceOwner@123456")
    lease = create_lease(client, "SN-PHY-LEASE-014")
    client.post("/api/v1/auth/logout")
    login(client, "admin", "Admin@123456")

    force_release_response = client.post(f"/api/v1/leases/{lease['lease_id']}/force-release")
    second_lease_response = client.post(
        "/api/v1/leases",
        json={
            "resource_code": "SN-PHY-LEASE-014",
            "duration_minutes": 60,
            "purpose": "after force release",
        },
    )

    assert force_release_response.status_code == 200
    assert force_release_response.json()["status"] == "RELEASED"
    assert second_lease_response.status_code == 201

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        events = list(
            session.scalars(
                select(ResourceLeaseEvent)
                .where(ResourceLeaseEvent.lease_id == lease["lease_id"])
                .order_by(ResourceLeaseEvent.id)
            )
        )
        assert [event.event_type for event in events] == [
            LeaseEventType.CREATED,
            LeaseEventType.FORCE_RELEASED,
        ]
        assert events[-1].actor_user.username == "admin"
        assert events[-1].target_user.username == "te-force-owner"


def test_te_cannot_force_release_and_inactive_lease_cannot_be_force_released(
    client: TestClient,
) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-force-owner2", "TeForceOwner2@123456", "TE")
    create_user(client, "te-force-other", "TeForceOther@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-015")
    client.post("/api/v1/auth/logout")
    login(client, "te-force-owner2", "TeForceOwner2@123456")
    lease = create_lease(client, "SN-PHY-LEASE-015")
    client.post("/api/v1/auth/logout")
    login(client, "te-force-other", "TeForceOther@123456")

    te_force_response = client.post(f"/api/v1/leases/{lease['lease_id']}/force-release")

    client.post("/api/v1/auth/logout")
    login(client, "admin", "Admin@123456")
    first_force_response = client.post(f"/api/v1/leases/{lease['lease_id']}/force-release")
    second_force_response = client.post(f"/api/v1/leases/{lease['lease_id']}/force-release")

    assert te_force_response.status_code == 403
    assert first_force_response.status_code == 200
    assert second_force_response.status_code == 409
    assert second_force_response.json()["detail"]["error_code"] == "LEASE_NOT_ACTIVE"


def test_admin_can_query_lease_events_with_after_id_but_te_cannot(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-event-owner", "TeEventOwner@123456", "TE")
    create_user(client, "te-event-viewer", "TeEventViewer@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-016")
    client.post("/api/v1/auth/logout")
    login(client, "te-event-owner", "TeEventOwner@123456")
    lease = create_lease(client, "SN-PHY-LEASE-016")
    client.post(
        f"/api/v1/leases/{lease['lease_id']}/extend",
        json={"duration_minutes": 30},
    )
    client.post("/api/v1/auth/logout")
    login(client, "te-event-viewer", "TeEventViewer@123456")

    te_events_response = client.get("/api/v1/lease-events")

    client.post("/api/v1/auth/logout")
    login(client, "admin", "Admin@123456")
    all_events_response = client.get("/api/v1/lease-events")
    first_event_id = all_events_response.json()[0]["id"]
    incremental_events_response = client.get(
        "/api/v1/lease-events",
        params={"after_id": first_event_id, "limit": 10},
    )

    assert te_events_response.status_code == 403
    assert all_events_response.status_code == 200
    assert [event["event_type"] for event in all_events_response.json()] == [
        "CREATED",
        "EXTENDED",
    ]
    assert incremental_events_response.status_code == 200
    assert [event["event_type"] for event in incremental_events_response.json()] == ["EXTENDED"]


def test_user_cannot_release_another_users_lease(client: TestClient) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-owner2", "TeOwner2@123456", "TE")
    create_user(client, "te-other", "TeOther@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-006")
    client.post("/api/v1/auth/logout")
    login(client, "te-owner2", "TeOwner2@123456")
    lease = create_lease(client, "SN-PHY-LEASE-006")
    client.post("/api/v1/auth/logout")
    login(client, "te-other", "TeOther@123456")

    release_response = client.post(f"/api/v1/leases/{lease['lease_id']}/release")

    assert release_response.status_code == 403
    assert release_response.json()["detail"]["error_code"] == "LEASE_NOT_OWNED"


def test_expired_lease_is_lazy_expired_and_no_longer_blocks_machine(
    client: TestClient,
) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "te-expired", "TeExpired@123456", "TE")
    create_pool_and_machine(client, "SN-PHY-LEASE-007")
    client.post("/api/v1/auth/logout")
    login(client, "te-expired", "TeExpired@123456")
    first_lease = create_lease(client, "SN-PHY-LEASE-007")

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        lease = session.scalar(
            select(ResourceLease).where(ResourceLease.lease_id == first_lease["lease_id"])
        )
        assert lease is not None
        lease.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    second_lease_response = client.post(
        "/api/v1/leases",
        json={
            "resource_code": "SN-PHY-LEASE-007",
            "duration_minutes": 60,
            "purpose": "after expiry",
        },
    )
    my_leases_response = client.get("/api/v1/leases/my")

    assert second_lease_response.status_code == 201
    leases_by_id = {item["lease_id"]: item for item in my_leases_response.json()}
    assert leases_by_id[first_lease["lease_id"]]["status"] == "EXPIRED"

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        events = list(
            session.scalars(
                select(ResourceLeaseEvent)
                .where(ResourceLeaseEvent.lease_id == first_lease["lease_id"])
                .order_by(ResourceLeaseEvent.id)
            )
        )
        assert [event.event_type for event in events] == [
            LeaseEventType.CREATED,
            LeaseEventType.EXPIRED,
        ]

    client.get("/api/v1/leases/my")

    with session_factory() as session:
        event_count = len(
            list(
                session.scalars(
                    select(ResourceLeaseEvent).where(
                        ResourceLeaseEvent.lease_id == first_lease["lease_id"]
                    )
                )
            )
        )
        assert event_count == 2
