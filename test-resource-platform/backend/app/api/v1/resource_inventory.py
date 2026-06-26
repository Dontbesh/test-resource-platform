from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.authorization import require_roles
from app.auth.dependencies import get_current_user, get_db
from app.identity.models import User, UserRole
from app.leases.service import list_active_machine_users
from app.resources.models import MachineResource, ResourceAdminStatus, ResourcePool
from app.resources.schemas import (
    MachineOccupancyStatus,
    MachineResourceCreateRequest,
    MachineResourcePublic,
    ResourcePoolCreateRequest,
    ResourcePoolPublic,
)
from app.resources.service import (
    create_machine_resource,
    create_resource_pool,
    get_machine_by_resource_code,
    get_resource_pool_by_id,
    get_resource_pool_by_name,
    list_machine_resources,
    list_resource_pools,
    set_machine_admin_status,
    set_resource_pool_active,
)

router = APIRouter()
require_inventory_maintainer = require_roles(UserRole.ADMIN, UserRole.TSE)


@router.get("/resource-pools", response_model=list[ResourcePoolPublic])
def list_pools(
    _: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ResourcePool]:
    return list_resource_pools(session)


@router.post(
    "/resource-pools",
    response_model=ResourcePoolPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_pool(
    body: ResourcePoolCreateRequest,
    _: Annotated[User, Depends(require_inventory_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> ResourcePool:
    if get_resource_pool_by_name(session, body.name) is not None:
        raise_resource_pool_name_exists()
    try:
        pool = create_resource_pool(session, body)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_resource_pool_name_exists()
    return pool


@router.get("/machines", response_model=list[MachineResourcePublic])
def list_machines(
    _: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[MachineResourcePublic]:
    active_machine_users = list_active_machine_users(session)
    machines = []
    for machine in list_machine_resources(session):
        leased_by_username = active_machine_users.get(machine.id)
        machine_public = MachineResourcePublic.model_validate(machine)
        if leased_by_username is not None:
            machine_public = machine_public.model_copy(
                update={
                    "occupancy_status": MachineOccupancyStatus.OCCUPIED,
                    "leased_by_username": leased_by_username,
                }
            )
        machines.append(machine_public)
    session.commit()
    return machines


@router.post("/machines", response_model=MachineResourcePublic, status_code=status.HTTP_201_CREATED)
def create_machine(
    body: MachineResourceCreateRequest,
    _: Annotated[User, Depends(require_inventory_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> MachineResource:
    pool = get_resource_pool_by_id(session, body.pool_id)
    if pool is None:
        raise_resource_pool_not_found()
    if not pool.is_active:
        raise_resource_pool_disabled()
    if get_machine_by_resource_code(session, body.resource_code) is not None:
        raise_resource_code_exists()
    try:
        machine = create_machine_resource(session, body)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_resource_code_exists()
    return machine


@router.post("/resource-pools/{pool_id}/disable", response_model=ResourcePoolPublic)
def disable_pool(
    pool_id: int,
    _: Annotated[User, Depends(require_inventory_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> ResourcePool:
    pool = get_resource_pool_by_id(session, pool_id)
    if pool is None:
        raise_resource_pool_not_found()
    set_resource_pool_active(session, pool, False)
    session.commit()
    return pool


@router.post("/resource-pools/{pool_id}/enable", response_model=ResourcePoolPublic)
def enable_pool(
    pool_id: int,
    _: Annotated[User, Depends(require_inventory_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> ResourcePool:
    pool = get_resource_pool_by_id(session, pool_id)
    if pool is None:
        raise_resource_pool_not_found()
    set_resource_pool_active(session, pool, True)
    session.commit()
    return pool


@router.post("/machines/{resource_code}/disable", response_model=MachineResourcePublic)
def disable_machine(
    resource_code: str,
    _: Annotated[User, Depends(require_inventory_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> MachineResource:
    machine = get_machine_by_resource_code(session, resource_code)
    if machine is None:
        raise_machine_not_found()
    set_machine_admin_status(session, machine, ResourceAdminStatus.DISABLED)
    session.commit()
    return machine


@router.post("/machines/{resource_code}/enable", response_model=MachineResourcePublic)
def enable_machine(
    resource_code: str,
    _: Annotated[User, Depends(require_inventory_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> MachineResource:
    machine = get_machine_by_resource_code(session, resource_code)
    if machine is None:
        raise_machine_not_found()
    pool = get_resource_pool_by_id(session, machine.pool_id)
    if pool is None:
        raise_resource_pool_not_found()
    if not pool.is_active:
        raise_resource_pool_disabled()
    set_machine_admin_status(session, machine, ResourceAdminStatus.ACTIVE)
    session.commit()
    return machine


def raise_resource_pool_name_exists() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error_code": "RESOURCE_POOL_NAME_ALREADY_EXISTS",
            "message": "Resource pool name already exists.",
        },
    )


def raise_resource_pool_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "RESOURCE_POOL_NOT_FOUND", "message": "Resource pool not found."},
    )


def raise_resource_pool_disabled() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error_code": "RESOURCE_POOL_DISABLED", "message": "Resource pool is disabled."},
    )


def raise_resource_code_exists() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error_code": "RESOURCE_CODE_ALREADY_EXISTS",
            "message": "Resource code already exists.",
        },
    )


def raise_machine_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "MACHINE_NOT_FOUND", "message": "Machine not found."},
    )
