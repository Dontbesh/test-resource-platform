from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.identity.models import User
from app.leases.models import LeaseStatus, ResourceLease
from app.leases.schemas import ResourceLeaseCreateRequest
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


def list_active_machine_users(
    session: Session,
    now: datetime | None = None,
) -> dict[int, str]:
    expire_overdue_leases(session, now or datetime.now(UTC))
    active_leases = session.scalars(
        select(ResourceLease)
        .options(joinedload(ResourceLease.user))
        .where(ResourceLease.status == LeaseStatus.ACTIVE)
    )
    return {lease.machine_id: lease.user.username for lease in active_leases}


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
    session.flush()
    return lease


def get_resource_lease_by_lease_id(session: Session, lease_id: str) -> ResourceLease | None:
    return session.scalar(
        select(ResourceLease)
        .options(joinedload(ResourceLease.machine), joinedload(ResourceLease.user))
        .where(ResourceLease.lease_id == lease_id)
    )


def expire_overdue_leases(session: Session, now: datetime) -> None:
    active_leases = session.scalars(
        select(ResourceLease).where(ResourceLease.status == LeaseStatus.ACTIVE)
    )
    for lease in active_leases:
        expires_at = _as_aware_utc(lease.expires_at)
        if expires_at <= now:
            lease.status = LeaseStatus.EXPIRED
    session.flush()


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
