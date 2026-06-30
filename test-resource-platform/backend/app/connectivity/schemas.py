from enum import StrEnum

from pydantic import BaseModel


class ConnectivityCheckStatus(StrEnum):
    REACHABLE = "REACHABLE"
    UNREACHABLE = "UNREACHABLE"


class ConnectivityTarget(StrEnum):
    SSH = "SSH"
    BMC_HTTPS = "BMC_HTTPS"


class ConnectivityCheckResult(BaseModel):
    target: ConnectivityTarget
    host: str
    port: int
    status: ConnectivityCheckStatus
    latency_ms: int | None
    error: str | None


class MachineConnectivityCheckResponse(BaseModel):
    resource_code: str
    checks: list[ConnectivityCheckResult]
