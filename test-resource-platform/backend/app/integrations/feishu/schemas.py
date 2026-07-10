from datetime import datetime

from pydantic import BaseModel, Field

from app.integrations.feishu.models import (
    FeishuAppStatus,
    FeishuPlatformType,
    FeishuSetupStatus,
)


class FeishuSetupBeginResponse(BaseModel):
    id: int
    device_code: str
    qr_url: str
    interval: int
    expires_in: int
    expires_at: datetime


class FeishuSetupPollRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=256)
    base_url: str | None = Field(default=None, max_length=256)


class FeishuSetupPollResponse(BaseModel):
    status: FeishuSetupStatus
    base_url: str
    app_id: str | None = None
    app_secret: str | None = None
    platform: FeishuPlatformType | None = None
    owner_open_id: str | None = None
    slow_down: bool = False
    error: str | None = None


class FeishuSetupSaveRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    platform_type: FeishuPlatformType
    app_id: str = Field(min_length=1, max_length=128)
    app_secret: str = Field(min_length=1, max_length=512)
    owner_open_id: str | None = Field(default=None, max_length=128)
    tenant_brand: str | None = Field(default=None, max_length=64)


class FeishuAppPublic(BaseModel):
    id: int
    name: str
    platform_type: FeishuPlatformType
    app_id: str
    owner_open_id: str | None
    tenant_brand: str | None
    bot_open_id: str | None
    status: FeishuAppStatus
    last_connected_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
