from pydantic import BaseModel, Field

from app.identity.models import UserRole


class UserPublic(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole


class UserPasswordResetRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)
