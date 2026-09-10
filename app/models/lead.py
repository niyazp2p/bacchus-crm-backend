import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class LeadTier(str, enum.Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"

class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    CONTACTED = "CONTACTED"
    NEGOTIATION = "NEGOTIATION"
    CONVERTED = "CONVERTED"
    LOST = "LOST"

class CommercialModel(str, enum.Enum):
    DISTRIBUTION = "DISTRIBUTION"
    PRIVATE_LABEL = "PRIVATE_LABEL"
    STATE_OWNERSHIP = "STATE_OWNERSHIP"

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    commercial_model: Mapped[CommercialModel] = mapped_column(Enum(CommercialModel), nullable=False)
    volume_estimate: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "6 Containers/mo"
    
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tier: Mapped[LeadTier] = mapped_column(Enum(LeadTier), default=LeadTier.COLD, index=True, nullable=False)
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.NEW, index=True, nullable=False)
    loss_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    assigned_to = relationship("User", back_populates="assigned_leads")
    follow_ups = relationship("FollowUp", back_populates="lead", cascade="all, delete-orphan")
    activities = relationship("LeadActivity", back_populates="lead", cascade="all, delete-orphan")
    conversion = relationship("Conversion", back_populates="lead", uselist=False)