from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.authorization import require_roles
from app.auth.dependencies import get_current_user, get_db
from app.identity.models import User, UserRole
from app.leases.models import ResourceLease
from app.leases.schemas import (
    ResourceLeaseCreateRequest,
    ResourceLeaseEventPublic,
    ResourceLeaseExtendRequest,
    ResourceLeasePublic,
)
from app.leases.service import (
    LeaseNotActiveError,
    LeaseNotFoundError,
    LeaseNotOwnedError,
    MachineNotAvailableError,
    MachineNotFoundError,
    ResourceAlreadyLeasedError,
    ResourcePoolDisabledError,
    create_resource_lease,
    extend_resource_lease,
    force_release_resource_lease,
    list_lease_events,
    list_user_leases,
    release_resource_lease,
)

router = APIRouter()
require_lease_operator = require_roles(UserRole.ADMIN, UserRole.TSE)


@router.post("/leases", response_model=ResourceLeasePublic, status_code=status.HTTP_201_CREATED)
def create_lease(
    body: ResourceLeaseCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ResourceLease:
    try:
        lease = create_resource_lease(session, body, current_user)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_resource_already_leased()
    except MachineNotFoundError:
        raise_machine_not_found()
    except ResourcePoolDisabledError:
        raise_resource_pool_disabled()
    except MachineNotAvailableError:
        raise_machine_not_available()
    except ResourceAlreadyLeasedError:
        raise_resource_already_leased()
    return lease


@router.get("/leases/my", response_model=list[ResourceLeasePublic])
def list_my_leases(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ResourceLease]:
    leases = list_user_leases(session, current_user)
    session.commit()
    return leases


@router.get("/lease-events", response_model=list[ResourceLeaseEventPublic])
def list_events(
    _: Annotated[User, Depends(require_lease_operator)],
    session: Annotated[Session, Depends(get_db)],
    after_id: int | None = None,
    limit: int = 100,
) -> list:
    bounded_limit = min(max(limit, 1), 200)
    return list_lease_events(session, after_id=after_id, limit=bounded_limit)


@router.post("/leases/{lease_id}/release", response_model=ResourceLeasePublic)
def release_lease(
    lease_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ResourceLease:
    try:
        lease = release_resource_lease(session, lease_id, current_user)
        session.commit()
    except LeaseNotFoundError:
        raise_lease_not_found()
    except LeaseNotOwnedError:
        raise_lease_not_owned()
    except LeaseNotActiveError:
        raise_lease_not_active()
    return lease


@router.post("/leases/{lease_id}/extend", response_model=ResourceLeasePublic)
def extend_lease(
    lease_id: str,
    body: ResourceLeaseExtendRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ResourceLease:
    try:
        lease = extend_resource_lease(session, lease_id, current_user, body)
        session.commit()
    except LeaseNotFoundError:
        raise_lease_not_found()
    except LeaseNotOwnedError:
        raise_lease_not_owned()
    except LeaseNotActiveError:
        raise_lease_not_active()
    return lease


@router.post("/leases/{lease_id}/force-release", response_model=ResourceLeasePublic)
def force_release_lease(
    lease_id: str,
    current_user: Annotated[User, Depends(require_lease_operator)],
    session: Annotated[Session, Depends(get_db)],
) -> ResourceLease:
    try:
        lease = force_release_resource_lease(session, lease_id, current_user)
        session.commit()
    except LeaseNotFoundError:
        raise_lease_not_found()
    except LeaseNotActiveError:
        raise_lease_not_active()
    return lease


def raise_machine_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "MACHINE_NOT_FOUND", "message": "Machine not found."},
    )


def raise_resource_pool_disabled() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error_code": "RESOURCE_POOL_DISABLED", "message": "Resource pool is disabled."},
    )


def raise_machine_not_available() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error_code": "MACHINE_NOT_AVAILABLE", "message": "Machine is not available."},
    )


def raise_resource_already_leased() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error_code": "RESOURCE_ALREADY_LEASED", "message": "Resource already leased."},
    )


def raise_lease_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "LEASE_NOT_FOUND", "message": "Lease not found."},
    )


def raise_lease_not_owned() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error_code": "LEASE_NOT_OWNED", "message": "Lease is not owned by user."},
    )


def raise_lease_not_active() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error_code": "LEASE_NOT_ACTIVE", "message": "Lease is not active."},
    )
