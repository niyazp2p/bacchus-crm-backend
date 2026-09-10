from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.follow_up import FollowUpStatus, FollowUpType

class FollowUpBase(BaseModel):
    lead_id: UUID
    scheduled_at: datetime
    type: FollowUpType = FollowUpType.CALL
    notes: str | None = None

class FollowUpCreate(FollowUpBase):
    pass

class FollowUpUpdate(BaseModel):
    scheduled_at: datetime | None = None
    type: FollowUpType | None = None
    status: FollowUpStatus | None = None
    notes: str | None = None

class FollowUpResponse(FollowUpBase):
    id: UUID
    user_id: UUID
    status: FollowUpStatus
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)