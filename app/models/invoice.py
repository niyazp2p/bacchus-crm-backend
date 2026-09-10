import enum
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, DateTime, ForeignKey, Numeric, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class PaymentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    VOID = "VOID"

class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    
    # Financial Aggregates
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)        # Sum of Amounts (Transaction Values)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)      # Sum of IGST
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)    # Subtotal + IGST
    
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.ISSUED, index=True, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    issued_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Compliance & Dispatch Party Records (JSONB snapshot)
    supply_country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    place_of_supply: Mapped[str] = mapped_column(String(100), nullable=False)
    billed_by_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    billed_to_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    
    sku_code: Mapped[str] = mapped_column(String(50), nullable=False)          # e.g., TAL-12-750, JC-WHISKY-750
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="Cases", nullable=False) # Cases, Bottles, Litres, Pallets
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Financial Math per row
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)          # quantity * rate
    gst_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)     # e.g., 18.00%
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)     # amount * (gst_percent / 100)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)      # amount + igst_amount

    # Relationships
    invoice = relationship("Invoice", back_populates="items")