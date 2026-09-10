from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.product import ProductCategory

class ProductBase(BaseModel):
    sku_code: str = Field(..., min_length=3, max_length=50, example="TAL-12-750")
    name: str = Field(..., min_length=2, max_length=200, example="Talsons' Reserve 12 Years")
    category: ProductCategory
    description: str | None = None
    unit: str = Field(default="Cases", max_length=30)
    bottle_volume: str = Field(default="750 ml", max_length=30)
    bottles_per_case: int = Field(default=12, gt=0)
    abv: str = Field(default="42.8% V/V", max_length=20)
    base_rate: Decimal = Field(..., gt=0, decimal_places=2, example=3500.00)
    default_gst_percent: Decimal = Field(default=Decimal("18.00"), ge=0, le=100, decimal_places=2)
    is_active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: str | None = None
    category: ProductCategory | None = None
    description: str | None = None
    unit: str | None = None
    bottle_volume: str | None = None
    bottles_per_case: int | None = None
    abv: str | None = None
    base_rate: Decimal | None = None
    default_gst_percent: Decimal | None = None
    is_active: bool | None = None

class ProductResponse(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)