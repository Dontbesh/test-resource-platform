from datetime import datetime

from pydantic import BaseModel, Field

from app.identity.schemas import UserPublic
from app.leases.models import LeaseEventType, LeaseStatus
from app.resources.schemas import MachineResourcePublic


class ResourceLeaseCreateRequest(BaseModel):
    resource_code: str = Field(min_length=1, max_length=128)
    duration_minutes: int = Field(ge=1, le=1440)
    purpose: str = Field(min_length=1, max_length=500)


class ResourceLeaseExtendRequest(BaseModel):
    duration_minutes: int = Field(ge=1, le=1440)


class ResourceLeasePublic(BaseModel):
    id: int
    lease_id: str
    machine: MachineResourcePublic
    user: UserPublic
    purpose: str
    status: LeaseStatus
    started_at: datetime
    expires_at: datetime
    released_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResourceLeaseEventPublic(BaseModel):
    id: int
    lease_id: str
    event_type: LeaseEventType
    actor_user: UserPublic
    target_user: UserPublic
    occurred_at: datetime
    previous_expires_at: datetime | None
    new_expires_at: datetime | None

    model_config = {"from_attributes": True}
