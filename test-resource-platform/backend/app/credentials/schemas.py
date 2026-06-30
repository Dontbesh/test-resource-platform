from pydantic import BaseModel, Field


class MachineCredentialUpsertRequest(BaseModel):
    ssh_username: str | None = Field(default=None, max_length=128)
    ssh_password: str | None = Field(default=None, max_length=512)
    bmc_username: str | None = Field(default=None, max_length=128)
    bmc_password: str | None = Field(default=None, max_length=512)


class MachineCredentialSummary(BaseModel):
    resource_code: str
    ssh_username: str | None
    has_ssh_password: bool
    bmc_username: str | None
    has_bmc_password: bool


class MachineCredentialSecret(BaseModel):
    resource_code: str
    ssh_username: str | None
    ssh_password: str | None
    bmc_username: str | None
    bmc_password: str | None
