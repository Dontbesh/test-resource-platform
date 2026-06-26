from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.authorization import require_roles
from app.auth.dependencies import get_current_user, get_db
from app.identity.models import User, UserRole
from app.resources.models import MachineResource, ResourcePool
from app.resources.schemas import (
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
) -> list[MachineResource]:
    return list_machine_resources(session)


@router.post("/machines", response_model=MachineResourcePublic, status_code=status.HTTP_201_CREATED)
def create_machine(
    body: MachineResourceCreateRequest,
    _: Annotated[User, Depends(require_inventory_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> MachineResource:
    if get_resource_pool_by_id(session, body.pool_id) is None:
        raise_resource_pool_not_found()
    if get_machine_by_resource_code(session, body.resource_code) is not None:
        raise_resource_code_exists()
    try:
        machine = create_machine_resource(session, body)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_resource_code_exists()
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


def raise_resource_code_exists() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error_code": "RESOURCE_CODE_ALREADY_EXISTS",
            "message": "Resource code already exists.",
        },
    )
