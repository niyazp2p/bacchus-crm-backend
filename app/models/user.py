import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class RoleType(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    SALES_DIRECTOR = "SALES_DIRECTOR"
    TERRITORY_REP = "TERRITORY_REP"
    FINANCE_OFFICER = "FINANCE_OFFICER"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleType] = mapped_column(Enum(RoleType), default=RoleType.TERRITORY_REP, nullable=False)
    territory: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "Africa-East", "Domestic-North"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    assigned_leads = relationship("Lead", back_populates="assigned_to")
    follow_ups = relationship("FollowUp", back_populates="user")
    activities = relationship("LeadActivity", back_populates="user")
    managed_customers = relationship("Customer", back_populates="account_manager")
    audit_logs = relationship("AuditLog", back_populates="user")