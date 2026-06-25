from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.auth.sessions import issue_session_token
from app.core.config import Settings, get_settings
from app.identity.models import User
from app.identity.schemas import UserPublic
from app.identity.service import authenticate_user

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=UserPublic)
def login(
    body: LoginRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    user = authenticate_user(session, body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "INVALID_CREDENTIALS",
                "message": "Invalid username or password.",
            },
        )
    token = issue_session_token(
        user.id,
        settings.session_secret_key,
        settings.session_max_age_seconds,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )
    return user


@router.get("/me", response_model=UserPublic)
def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")
