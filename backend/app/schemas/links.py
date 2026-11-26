from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.core.constants import MAX_URL_LENGTH, SHORT_CODE_PATTERN
from app.core.exceptions import AppError


class LinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_url: StrictStr = Field(min_length=1, max_length=MAX_URL_LENGTH)
    custom_alias: None = None
    expires_at: None = None

    @field_validator("custom_alias", "expires_at", mode="before")
    @classmethod
    def reject_future_features(cls, value):
        if value is not None:
            raise AppError(
                422, "FEATURE_NOT_SUPPORTED", "Custom aliases and expiration are not supported yet."
            )
        return value


class LinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_url: str
    short_code: str = Field(pattern=SHORT_CODE_PATTERN)
    short_url: str
    is_active: bool
    created_at: datetime
    expires_at: None = None
