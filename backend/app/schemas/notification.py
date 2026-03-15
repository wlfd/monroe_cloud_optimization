from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


class NotificationChannelCreate(BaseModel):
    name: str
    channel_type: str  # 'email' | 'webhook'
    config_json: dict[str, Any]

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: str) -> str:
        if v not in ("email", "webhook"):
            raise ValueError("channel_type must be 'email' or 'webhook'")
        return v

    @field_validator("config_json")
    @classmethod
    def validate_config(cls, v: dict, info) -> dict:
        channel_type = info.data.get("channel_type")
        if channel_type == "email" and "address" not in v:
            raise ValueError("email channel requires config_json.address")
        if channel_type == "webhook" and "url" not in v:
            raise ValueError("webhook channel requires config_json.url")
        return v


class NotificationChannelResponse(BaseModel):
    id: UUID
    name: str
    channel_type: str
    config_json: dict[str, Any]
    owner_user_id: UUID | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def redact_secrets(self) -> "NotificationChannelResponse":
        if isinstance(self.config_json, dict) and "secret" in self.config_json:
            self.config_json = {**self.config_json, "secret": "***"}
        return self


class NotificationDeliveryResponse(BaseModel):
    id: UUID
    channel_id: UUID
    event_type: str
    event_id: UUID
    attempt_number: int
    attempted_at: datetime
    status: str
    response_code: int | None
    error_message: str | None

    model_config = {"from_attributes": True}
