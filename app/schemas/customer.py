from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.lead import CommercialModel

class CustomerBase(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    tax_identifier: str | None = Field(None, max_length=100)  # GST, VAT, or EIN
    country: str = Field(..., min_length=2, max_length=100)

class CustomerCreate(CustomerBase):
    account_manager_id: UUID | None = None

class CustomerUpdate(BaseModel):
    company_name: str | None = None
    tax_identifier: str | None = None
    country: str | None = None
    account_manager_id: UUID | None = None

class CustomerResponse(CustomerBase):
    id: UUID
    customer_code: str
    account_manager_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConversionCreate(BaseModel):
    lead_id: UUID
    deal_value: Decimal = Field(..., gt=0, decimal_places=2)
    commercial_model: CommercialModel
    tax_identifier: str | None = None

class ConversionResponse(BaseModel):
    id: UUID
    lead_id: UUID
    customer_id: UUID
    deal_value: Decimal
    commercial_model: CommercialModel
    converted_at: datetime
    customer: CustomerResponse

    model_config = ConfigDict(from_attributes=True)