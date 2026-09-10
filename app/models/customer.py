import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.lead import CommercialModel

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)  # GST, VAT, or EIN
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    
    account_manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    account_manager = relationship("User", back_populates="managed_customers")
    conversion = relationship(
        "Conversion",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    invoices = relationship(
        "Invoice",
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class Conversion(Base):
    __tablename__ = "conversions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    deal_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    commercial_model: Mapped[CommercialModel] = mapped_column(Enum(CommercialModel), nullable=False)
    converted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    lead = relationship("Lead", back_populates="conversion")
    customer = relationship("Customer", back_populates="conversion")