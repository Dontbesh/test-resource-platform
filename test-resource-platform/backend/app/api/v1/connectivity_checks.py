from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.connectivity.schemas import MachineConnectivityCheckResponse
from app.connectivity.service import MachineNotFoundError, check_machine_connectivity
from app.connectivity.tcp import TcpConnectivityChecker
from app.identity.models import User

router = APIRouter()


@router.post(
    "/machines/{resource_code}/connectivity-checks",
    response_model=MachineConnectivityCheckResponse,
)
def run_machine_connectivity_check(
    resource_code: str,
    _: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> MachineConnectivityCheckResponse:
    try:
        return check_machine_connectivity(
            session=session,
            resource_code=resource_code,
            checker=get_connectivity_checker(),
        )
    except MachineNotFoundError:
        raise_machine_not_found()


def get_connectivity_checker() -> TcpConnectivityChecker:
    return TcpConnectivityChecker()


def raise_machine_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "MACHINE_NOT_FOUND", "message": "Machine not found."},
    )
