from pydantic import BaseModel

from app.identity.models import UserRole


class UserPublic(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}
