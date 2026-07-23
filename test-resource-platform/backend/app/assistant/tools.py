import json
from enum import StrEnum

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.leases.service import list_active_machine_occupancy
from app.resources.models import ResourceAdminStatus, ResourceType
from app.resources.service import list_machine_resources, list_resource_pools


class MachineOccupancyFilter(StrEnum):
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"


class MachineSearchArguments(BaseModel):
    resource_type: ResourceType | None = None
    architecture: str | None = Field(default=None, max_length=64)
    os_name: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list, max_length=10)
    occupancy_status: MachineOccupancyFilter | None = None
    limit: int = Field(default=10, ge=1, le=20)


MACHINE_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_machines",
        "description": "Search machine inventory using structured, non-secret fields.",
        "parameters": {
            "type": "object",
            "properties": {
                "resource_type": {"type": "string", "enum": ["PHYSICAL", "VIRTUAL"]},
                "architecture": {"type": "string"},
                "os_name": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                "occupancy_status": {"type": "string", "enum": ["FREE", "OCCUPIED"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "additionalProperties": False,
        },
    },
}

ASSISTANT_TOOLS = [MACHINE_SEARCH_TOOL]


class AssistantToolError(Exception):
    pass


def execute_assistant_tool(
    session: Session,
    name: str,
    arguments_json: str,
) -> str:
    if name != "search_machines":
        raise AssistantToolError(f"Unsupported assistant tool: {name}")
    try:
        arguments = MachineSearchArguments.model_validate_json(arguments_json or "{}")
    except ValidationError as exc:
        raise AssistantToolError(f"Invalid search_machines arguments: {exc}") from exc
    return json.dumps(search_machines(session, arguments), ensure_ascii=False)


def search_machines(session: Session, arguments: MachineSearchArguments) -> dict:
    occupancy = list_active_machine_occupancy(session)
    pools = {pool.id: pool for pool in list_resource_pools(session)}
    results: list[dict] = []
    requested_tags = {tag.casefold() for tag in arguments.tags}

    for machine in list_machine_resources(session):
        pool = pools.get(machine.pool_id)
        is_occupied = machine.id in occupancy
        if arguments.resource_type and machine.resource_type != arguments.resource_type:
            continue
        if arguments.architecture and not same_text(machine.architecture, arguments.architecture):
            continue
        if arguments.os_name and not contains_text(machine.os_name, arguments.os_name):
            continue
        machine_tags = {tag.casefold() for tag in machine.tags}
        if requested_tags and not requested_tags.issubset(machine_tags):
            continue
        if arguments.occupancy_status == MachineOccupancyFilter.FREE:
            if (
                is_occupied
                or machine.admin_status != ResourceAdminStatus.ACTIVE
                or pool is None
                or not pool.is_active
            ):
                continue
        if arguments.occupancy_status == MachineOccupancyFilter.OCCUPIED and not is_occupied:
            continue

        results.append(
            {
                "resource_code": machine.resource_code,
                "name": machine.name,
                "resource_type": machine.resource_type,
                "pool": pool.name if pool else None,
                "architecture": machine.architecture,
                "os_name": machine.os_name,
                "tags": machine.tags,
                "admin_status": machine.admin_status,
                "connectivity_status": machine.connectivity_status,
                "occupancy_status": "OCCUPIED" if is_occupied else "FREE",
            }
        )
        if len(results) >= arguments.limit:
            break

    return {"count": len(results), "machines": results}


def same_text(actual: str | None, expected: str) -> bool:
    return actual is not None and actual.casefold() == expected.casefold()


def contains_text(actual: str | None, expected: str) -> bool:
    return actual is not None and expected.casefold() in actual.casefold()
