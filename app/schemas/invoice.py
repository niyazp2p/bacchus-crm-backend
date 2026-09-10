from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.invoice import PaymentStatus

class PartyDetails(BaseModel):
    name: str = Field(..., min_length=2, description="Legal entity name")
    address: str = Field(..., min_length=5, description="Full registered trade address")
    gstin: str = Field(..., min_length=15, max_length=15, description="15-character GSTIN")
    pan: str = Field(..., min_length=10, max_length=10, description="10-character PAN")
    email: EmailStr = Field(..., description="Official trade liaison email")
    phone: str = Field(..., min_length=8, description="Contact phone / mobile number")

class InvoiceItemCreate(BaseModel):
    sku_code: str = Field(..., min_length=2, max_length=50, example="TAL-12-750")
    description: str | None = Field(None, description="Optional custom description; defaults to master catalog name")
    unit: str = Field(default="Cases", max_length=30, example="Cases")
    quantity: int = Field(..., gt=0, example=500)
    rate: Decimal | None = Field(None, gt=0, decimal_places=2, description="Unit rate; defaults to master catalog base rate")
    gst_percent: Decimal | None = Field(None, ge=0, le=100, decimal_places=2, description="GST %; defaults to master catalog GST %")

class InvoiceItemResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    sku_code: str
    description: str
    unit: str
    quantity: int
    rate: Decimal
    amount: Decimal
    gst_percent: Decimal
    igst_amount: Decimal
    line_total: Decimal

    model_config = ConfigDict(from_attributes=True)

class InvoiceCreate(BaseModel):
    customer_id: UUID
    currency: str = Field(default="INR", max_length=10)
    due_date: datetime
    supply_country: str = Field(default="India", max_length=100)
    place_of_supply: str = Field(..., max_length=100, example="Punjab (State Code 03)")
    billed_by: PartyDetails | None = Field(
        None, 
        description="Optional custom seller party snapshot; defaults to Bacchus HQ"
    )
    billed_to: PartyDetails
    notes: str | None = Field(None, description="Commercial consignment remarks or export declarations")
    items: list[InvoiceItemCreate] = Field(..., min_length=1)

class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str
    customer_id: UUID
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: PaymentStatus
    due_date: datetime
    issued_date: datetime
    supply_country: str
    place_of_supply: str
    billed_by_snapshot: PartyDetails
    billed_to_snapshot: PartyDetails
    notes: str | None
    items: list[InvoiceItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class InvoiceStatusUpdate(BaseModel):
    status: PaymentStatus