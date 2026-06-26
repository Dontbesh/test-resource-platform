from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.resources.models import ConnectivityStatus, ResourceAdminStatus, ResourceType


class MachineOccupancyStatus(StrEnum):
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"


class ResourcePoolCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    location: str | None = Field(default=None, max_length=128)
    network_zone: str | None = Field(default=None, max_length=128)


class ResourcePoolPublic(BaseModel):
    id: int
    name: str
    description: str | None
    location: str | None
    network_zone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MachineResourceCreateRequest(BaseModel):
    resource_code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    resource_type: ResourceType
    pool_id: int
    host_machine_id: int | None = None
    is_critical: bool = False
    owner: str | None = Field(default=None, max_length=128)
    architecture: str | None = Field(default=None, max_length=64)
    os_name: str | None = Field(default=None, max_length=128)
    ip_address: str | None = Field(default=None, max_length=64)
    mac_address: str | None = Field(default=None, max_length=64)
    bmc_address: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list)


class MachineResourcePublic(BaseModel):
    id: int
    resource_code: str
    name: str
    resource_type: ResourceType
    pool_id: int
    host_machine_id: int | None
    admin_status: ResourceAdminStatus
    connectivity_status: ConnectivityStatus
    is_critical: bool
    owner: str | None
    architecture: str | None
    os_name: str | None
    ip_address: str | None
    mac_address: str | None
    bmc_address: str | None
    tags: list[str]
    occupancy_status: MachineOccupancyStatus = MachineOccupancyStatus.FREE
    leased_by_username: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
