from sqlalchemy import select
from sqlalchemy.orm import Session

from app.resources.models import MachineResource, ResourcePool
from app.resources.schemas import MachineResourceCreateRequest, ResourcePoolCreateRequest


def list_resource_pools(session: Session) -> list[ResourcePool]:
    return list(session.scalars(select(ResourcePool).order_by(ResourcePool.id)))


def get_resource_pool_by_id(session: Session, pool_id: int) -> ResourcePool | None:
    return session.get(ResourcePool, pool_id)


def get_resource_pool_by_name(session: Session, name: str) -> ResourcePool | None:
    return session.scalar(select(ResourcePool).where(ResourcePool.name == name))


def create_resource_pool(session: Session, body: ResourcePoolCreateRequest) -> ResourcePool:
    pool = ResourcePool(
        name=body.name,
        description=body.description,
        location=body.location,
        network_zone=body.network_zone,
    )
    session.add(pool)
    session.flush()
    return pool


def list_machine_resources(session: Session) -> list[MachineResource]:
    return list(session.scalars(select(MachineResource).order_by(MachineResource.id)))


def get_machine_by_resource_code(session: Session, resource_code: str) -> MachineResource | None:
    return session.scalar(
        select(MachineResource).where(MachineResource.resource_code == resource_code)
    )


def create_machine_resource(
    session: Session,
    body: MachineResourceCreateRequest,
) -> MachineResource:
    machine = MachineResource(
        resource_code=body.resource_code,
        name=body.name,
        resource_type=body.resource_type,
        pool_id=body.pool_id,
        host_machine_id=body.host_machine_id,
        is_critical=body.is_critical,
        owner=body.owner,
        architecture=body.architecture,
        os_name=body.os_name,
        ip_address=body.ip_address,
        mac_address=body.mac_address,
        bmc_address=body.bmc_address,
        tags=body.tags,
    )
    session.add(machine)
    session.flush()
    return machine
