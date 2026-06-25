from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.identity.models import User, UserRole


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed_roles = set(roles)

    def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "FORBIDDEN", "message": "Permission denied."},
            )
        return current_user

    return dependency


require_admin = require_roles(UserRole.ADMIN)
