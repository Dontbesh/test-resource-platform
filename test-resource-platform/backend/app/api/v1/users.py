from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.authorization import require_admin
from app.auth.dependencies import get_db
from app.identity.models import User
from app.identity.schemas import UserCreateRequest, UserPasswordResetRequest, UserPublic
from app.identity.service import (
    create_user,
    disable_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
    reset_user_password,
)

router = APIRouter(prefix="/users")


@router.get("", response_model=list[UserPublic])
def list_platform_users(
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db)],
) -> list[User]:
    return list_users(session)


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_platform_user(
    body: UserCreateRequest,
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    if get_user_by_username(session, body.username) is not None:
        raise_username_already_exists()
    try:
        user = create_user(session, body.username, body.password, body.role)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_username_already_exists()
    return user


@router.post("/{user_id}/disable", response_model=UserPublic)
def disable_platform_user(
    user_id: int,
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    user = get_user_by_id(session, user_id)
    if user is None:
        raise_user_not_found()
    disable_user(session, user)
    session.commit()
    return user


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_platform_user_password(
    user_id: int,
    body: UserPasswordResetRequest,
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db)],
) -> None:
    user = get_user_by_id(session, user_id)
    if user is None:
        raise_user_not_found()
    reset_user_password(session, user, body.password)
    session.commit()


def raise_user_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "USER_NOT_FOUND", "message": "User not found."},
    )


def raise_username_already_exists() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error_code": "USERNAME_ALREADY_EXISTS",
            "message": "Username already exists.",
        },
    )
