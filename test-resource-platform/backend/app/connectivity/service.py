from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectivity.schemas import (
    ConnectivityCheckResult,
    ConnectivityCheckStatus,
    ConnectivityTarget,
    MachineConnectivityCheckResponse,
)
from app.resources.models import MachineResource


class ConnectivityChecker(Protocol):
    def check(self, host: str, port: int, timeout_seconds: float) -> tuple[bool, int, str | None]:
        pass


class MachineNotFoundError(Exception):
    pass


def check_machine_connectivity(
    session: Session,
    resource_code: str,
    checker: ConnectivityChecker,
    timeout_seconds: float = 2.0,
) -> MachineConnectivityCheckResponse:
    machine = session.scalar(
        select(MachineResource).where(MachineResource.resource_code == resource_code)
    )
    if machine is None:
        raise MachineNotFoundError

    checks: list[ConnectivityCheckResult] = []
    if machine.ip_address:
        checks.append(
            run_check(
                checker=checker,
                target=ConnectivityTarget.SSH,
                host=machine.ip_address,
                port=22,
                timeout_seconds=timeout_seconds,
            )
        )
    if machine.bmc_address:
        checks.append(
            run_check(
                checker=checker,
                target=ConnectivityTarget.BMC_HTTPS,
                host=machine.bmc_address,
                port=443,
                timeout_seconds=timeout_seconds,
            )
        )
    return MachineConnectivityCheckResponse(resource_code=machine.resource_code, checks=checks)


def run_check(
    checker: ConnectivityChecker,
    target: ConnectivityTarget,
    host: str,
    port: int,
    timeout_seconds: float,
) -> ConnectivityCheckResult:
    is_reachable, latency_ms, error = checker.check(host, port, timeout_seconds)
    return ConnectivityCheckResult(
        target=target,
        host=host,
        port=port,
        status=(
            ConnectivityCheckStatus.REACHABLE
            if is_reachable
            else ConnectivityCheckStatus.UNREACHABLE
        ),
        latency_ms=latency_ms,
        error=error,
    )
