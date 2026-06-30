from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.identity.models import User
from app.leases.models import LeaseEventType, LeaseStatus, ResourceLease, ResourceLeaseEvent
from app.leases.schemas import ResourceLeaseCreateRequest, ResourceLeaseExtendRequest
from app.resources.models import MachineResource, ResourceAdminStatus, ResourcePool


class MachineNotFoundError(Exception):
    pass


class ResourcePoolDisabledError(Exception):
    pass


class MachineNotAvailableError(Exception):
    pass


class ResourceAlreadyLeasedError(Exception):
    pass


class LeaseNotFoundError(Exception):
    pass


class LeaseNotOwnedError(Exception):
    pass


class LeaseNotActiveError(Exception):
    pass


def create_resource_lease(
    session: Session,
    body: ResourceLeaseCreateRequest,
    user: User,
    now: datetime | None = None,
) -> ResourceLease:
    current_time = now or datetime.now(UTC)
    expire_overdue_leases(session, current_time)

    machine = session.scalar(
        select(MachineResource).where(MachineResource.resource_code == body.resource_code)
    )
    if machine is None:
        raise MachineNotFoundError

    pool = session.get(ResourcePool, machine.pool_id)
    if pool is None or not pool.is_active:
        raise ResourcePoolDisabledError

    if machine.admin_status != ResourceAdminStatus.ACTIVE:
        raise MachineNotAvailableError

    active_lease = session.scalar(
        select(ResourceLease)
        .where(ResourceLease.machine_id == machine.id)
        .where(ResourceLease.status == LeaseStatus.ACTIVE)
    )
    if active_lease is not None:
        raise ResourceAlreadyLeasedError

    lease = ResourceLease(
        lease_id=f"lease_{uuid4().hex}",
        machine_id=machine.id,
        user_id=user.id,
        purpose=body.purpose,
        status=LeaseStatus.ACTIVE,
        started_at=current_time,
        expires_at=current_time + timedelta(minutes=body.duration_minutes),
    )
    session.add(lease)
    session.flush()
    append_lease_event(
        session,
        lease=lease,
        event_type=LeaseEventType.CREATED,
        actor_user=user,
        occurred_at=current_time,
        new_expires_at=lease.expires_at,
    )
    session.flush()
    return get_resource_lease_by_lease_id(session, lease.lease_id) or lease


def list_user_leases(
    session: Session,
    user: User,
    now: datetime | None = None,
) -> list[ResourceLease]:
    expire_overdue_leases(session, now or datetime.now(UTC))
    return list(
        session.scalars(
            select(ResourceLease)
            .options(joinedload(ResourceLease.machine), joinedload(ResourceLease.user))
            .where(ResourceLease.user_id == user.id)
            .order_by(ResourceLease.created_at.desc(), ResourceLease.id.desc())
        )
    )


def list_active_machine_occupancy(
    session: Session,
    now: datetime | None = None,
) -> dict[int, tuple[str, str]]:
    expire_overdue_leases(session, now or datetime.now(UTC))
    active_leases = session.scalars(
        select(ResourceLease)
        .options(joinedload(ResourceLease.user))
        .where(ResourceLease.status == LeaseStatus.ACTIVE)
    )
    return {lease.machine_id: (lease.user.username, lease.lease_id) for lease in active_leases}


def list_active_machine_users(
    session: Session,
    now: datetime | None = None,
) -> dict[int, str]:
    return {
        machine_id: username
        for machine_id, (username, _) in list_active_machine_occupancy(session, now).items()
    }


def list_lease_events(
    session: Session,
    after_id: int | None = None,
    limit: int = 100,
) -> list[ResourceLeaseEvent]:
    query = select(ResourceLeaseEvent).options(
        joinedload(ResourceLeaseEvent.actor_user),
        joinedload(ResourceLeaseEvent.target_user),
    )
    if after_id is not None:
        query = query.where(ResourceLeaseEvent.id > after_id)
    query = query.order_by(ResourceLeaseEvent.id.asc()).limit(limit)
    return list(session.scalars(query))


def release_resource_lease(
    session: Session,
    lease_id: str,
    user: User,
    now: datetime | None = None,
) -> ResourceLease:
    current_time = now or datetime.now(UTC)
    expire_overdue_leases(session, current_time)
    lease = get_resource_lease_by_lease_id(session, lease_id)
    if lease is None:
        raise LeaseNotFoundError
    if lease.user_id != user.id:
        raise LeaseNotOwnedError
    if lease.status != LeaseStatus.ACTIVE:
        raise LeaseNotActiveError

    lease.status = LeaseStatus.RELEASED
    lease.released_at = current_time
    append_lease_event(
        session,
        lease=lease,
        event_type=LeaseEventType.RELEASED,
        actor_user=user,
        occurred_at=current_time,
        previous_expires_at=lease.expires_at,
        new_expires_at=lease.expires_at,
    )
    session.flush()
    return lease


def extend_resource_lease(
    session: Session,
    lease_id: str,
    user: User,
    body: ResourceLeaseExtendRequest,
    now: datetime | None = None,
) -> ResourceLease:
    current_time = now or datetime.now(UTC)
    expire_overdue_leases(session, current_time)
    lease = get_resource_lease_by_lease_id(session, lease_id)
    if lease is None:
        raise LeaseNotFoundError
    if lease.user_id != user.id:
        raise LeaseNotOwnedError
    if lease.status != LeaseStatus.ACTIVE:
        raise LeaseNotActiveError

    previous_expires_at = lease.expires_at
    lease.expires_at = _as_aware_utc(lease.expires_at) + timedelta(minutes=body.duration_minutes)
    append_lease_event(
        session,
        lease=lease,
        event_type=LeaseEventType.EXTENDED,
        actor_user=user,
        occurred_at=current_time,
        previous_expires_at=previous_expires_at,
        new_expires_at=lease.expires_at,
    )
    session.flush()
    return lease


def force_release_resource_lease(
    session: Session,
    lease_id: str,
    actor_user: User,
    now: datetime | None = None,
) -> ResourceLease:
    current_time = now or datetime.now(UTC)
    expire_overdue_leases(session, current_time)
    lease = get_resource_lease_by_lease_id(session, lease_id)
    if lease is None:
        raise LeaseNotFoundError
    if lease.status != LeaseStatus.ACTIVE:
        raise LeaseNotActiveError

    lease.status = LeaseStatus.RELEASED
    lease.released_at = current_time
    append_lease_event(
        session,
        lease=lease,
        event_type=LeaseEventType.FORCE_RELEASED,
        actor_user=actor_user,
        occurred_at=current_time,
        previous_expires_at=lease.expires_at,
        new_expires_at=lease.expires_at,
    )
    session.flush()
    return lease


def get_resource_lease_by_lease_id(session: Session, lease_id: str) -> ResourceLease | None:
    return session.scalar(
        select(ResourceLease)
        .options(joinedload(ResourceLease.machine), joinedload(ResourceLease.user))
        .where(ResourceLease.lease_id == lease_id)
    )


def append_lease_event(
    session: Session,
    lease: ResourceLease,
    event_type: LeaseEventType,
    actor_user: User,
    occurred_at: datetime,
    previous_expires_at: datetime | None = None,
    new_expires_at: datetime | None = None,
) -> ResourceLeaseEvent:
    event = ResourceLeaseEvent(
        lease_id=lease.lease_id,
        resource_lease_id=lease.id,
        machine_id=lease.machine_id,
        actor_user_id=actor_user.id,
        target_user_id=lease.user_id,
        event_type=event_type,
        occurred_at=occurred_at,
        previous_expires_at=previous_expires_at,
        new_expires_at=new_expires_at,
    )
    session.add(event)
    return event


def expire_overdue_leases(session: Session, now: datetime) -> None:
    active_leases = session.scalars(
        select(ResourceLease).where(ResourceLease.status == LeaseStatus.ACTIVE)
    )
    for lease in active_leases:
        expires_at = _as_aware_utc(lease.expires_at)
        if expires_at <= now:
            lease.status = LeaseStatus.EXPIRED
            append_lease_event(
                session,
                lease=lease,
                event_type=LeaseEventType.EXPIRED,
                actor_user=lease.user,
                occurred_at=now,
                previous_expires_at=lease.expires_at,
                new_expires_at=lease.expires_at,
            )
    session.flush()


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
