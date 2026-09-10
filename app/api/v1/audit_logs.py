import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_roles
from app.models.user import User, RoleType
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Administrative Governance & Audit"])

@router.get("", response_model=list[AuditLogResponse])
async def list_audit_trail(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN]))],
    method: str | None = Query(None, example="POST"),
    user_email: str | None = Query(None),
    status_code: int | None = Query(None),
    endpoint: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(AuditLog)

    if method:
        stmt = stmt.where(AuditLog.method == method.upper())
    if user_email:
        stmt = stmt.where(AuditLog.user_email.ilike(f"%{user_email}%"))
    if status_code:
        stmt = stmt.where(AuditLog.status_code == status_code)
    if endpoint:
        stmt = stmt.where(AuditLog.endpoint.ilike(f"%{endpoint}%"))

    stmt = stmt.order_by(desc(AuditLog.timestamp)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()