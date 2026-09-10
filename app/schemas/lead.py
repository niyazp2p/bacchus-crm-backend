from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from app.models.lead import CommercialModel, LeadStatus, LeadTier

class LeadBase(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    contact_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = None
    country: str = Field(..., min_length=2, max_length=100)
    state: str | None = None
    commercial_model: CommercialModel
    volume_estimate: str | None = None

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    company_name: str | None = None
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    country: str | None = None
    state: str | None = None
    commercial_model: CommercialModel | None = None
    volume_estimate: str | None = None
    status: LeadStatus | None = None
    assigned_to_id: UUID | None = None
    loss_reason: str | None = None

class LeadResponse(LeadBase):
    id: UUID
    lead_code: str
    score: int
    tier: LeadTier
    status: LeadStatus
    loss_reason: str | None = None
    assigned_to_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LeadFilterParams(BaseModel):
    tier: LeadTier | None = None
    status: LeadStatus | None = None
    commercial_model: CommercialModel | None = None
    country: str | None = None
    assigned_to_id: UUID | None = None