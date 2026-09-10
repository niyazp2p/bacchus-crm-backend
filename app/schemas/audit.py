from datetime import datetime
from uuid import UUID
from typing import Any
from pydantic import BaseModel, ConfigDict

class AuditLogResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    user_email: str | None
    user_role: str | None
    method: str
    endpoint: str
    status_code: int
    client_ip: str | None
    user_agent: str | None
    execution_time_ms: float
    meta_data: dict[str, Any] | None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)