from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.identity.models import User, UserRole
from app.identity.passwords import hash_password, verify_password


def count_users(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(User)) or 0


def create_user(session: Session, username: str, password: str, role: UserRole) -> User:
    user = User(username=username, password_hash=hash_password(password), role=role, is_active=True)
    session.add(user)
    session.flush()
    return user


def get_user_by_username(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == username))


def get_user_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def list_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).order_by(User.id)))


def disable_user(session: Session, user: User) -> User:
    user.is_active = False
    session.flush()
    return user


def reset_user_password(session: Session, user: User, password: str) -> None:
    user.password_hash = hash_password(password)
    session.flush()


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(session, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
