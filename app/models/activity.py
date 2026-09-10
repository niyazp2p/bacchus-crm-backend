import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class ActivityType(str, enum.Enum):
    NOTE = "NOTE"
    CALL_LOG = "CALL_LOG"
    EMAIL_SENT = "EMAIL_SENT"
    MEETING = "MEETING"
    STATUS_CHANGE = "STATUS_CHANGE"
    ASSIGNMENT = "ASSIGNMENT"

class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), nullable=False)
    meta_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Stores diffs, minutes, or change snapshots
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    # Relationships
    lead = relationship("Lead", back_populates="activities")
    user = relationship("User", back_populates="activities")