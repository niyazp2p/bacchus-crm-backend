import enum
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Numeric, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class ProductCategory(str, enum.Enum):
    SINGLE_MALT = "SINGLE_MALT"
    BLENDED_WHISKY = "BLENDED_WHISKY"
    VODKA = "VODKA"
    RUM = "RUM"
    GIN = "GIN"
    RTD = "RTD"

class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)  # e.g., TAL-12-750
    name: Mapped[str] = mapped_column(String(200), nullable=False)                             # e.g., Talsons' Reserve 12 Years
    category: Mapped[ProductCategory] = mapped_column(Enum(ProductCategory), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Unit & Packing
    unit: Mapped[str] = mapped_column(String(30), default="Cases", nullable=False)             # Cases, Bottles
    bottle_volume: Mapped[str] = mapped_column(String(30), default="750 ml", nullable=False)   # 750 ml, 375 ml, 180 ml
    bottles_per_case: Mapped[int] = mapped_column(default=12, nullable=False)
    abv: Mapped[str] = mapped_column(String(20), default="42.8% V/V", nullable=False)
    
    # Financial Commercials
    base_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)                  # Base price per unit
    default_gst_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("18.00"), nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)