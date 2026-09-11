from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class ContactInquiryPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = "General Corporate Inquiries"
    message: str = Field(..., min_length=1, max_length=5000)

class ContactInquiryResponse(BaseModel):
    success: bool
    reference_code: str
    message: str
    received_at: datetime