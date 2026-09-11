from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class ContactInquiryPayload(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    category: str = Field(..., min_length=3, max_length=100)
    message: str = Field(..., min_length=5, max_length=3000)

class ContactInquiryResponse(BaseModel):
    success: bool
    reference_code: str
    message: str
    received_at: datetime