from datetime import datetime
from uuid import UUID
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.activity import ActivityType

class ActivityBase(BaseModel):
    lead_id: UUID
    type: ActivityType
    meta_data: dict[str, Any] | None = Field(default_factory=dict)

class ActivityCreate(ActivityBase):
    pass

class ActivityResponse(ActivityBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)