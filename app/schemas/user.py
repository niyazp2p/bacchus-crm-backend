from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict
from app.models.user import RoleType

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: RoleType
    territory: str | None = None
    is_active: bool = True

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: RoleType = RoleType.TERRITORY_REP
    territory: str | None = None

class UserUpdate(BaseModel):
    name: str | None = None
    territory: str | None = None

class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str

class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)