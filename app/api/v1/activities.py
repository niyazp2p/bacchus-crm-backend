import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User, RoleType
from app.models.lead import Lead
from app.models.activity import LeadActivity, ActivityType
from app.schemas.activity import ActivityCreate, ActivityResponse

router = APIRouter(prefix="/activities", tags=["Lead Activities"])

@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def log_activity(
    payload: ActivityCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    stmt = select(Lead).where(Lead.id == payload.lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead does not exist.")

    if current_user.role == RoleType.TERRITORY_REP and lead.assigned_to_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot log activity on unassigned lead.")

    activity = LeadActivity(
        lead_id=payload.lead_id,
        user_id=current_user.id,
        type=payload.type,
        meta_data=payload.meta_data,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)
    return activity

@router.get("/lead/{lead_id}", response_model=list[ActivityResponse])
async def get_lead_timeline(
    lead_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    activity_type: ActivityType | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    # Verify lead access
    stmt = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")

    if current_user.role == RoleType.TERRITORY_REP and lead.assigned_to_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to lead timeline.")

    activity_stmt = select(LeadActivity).where(LeadActivity.lead_id == lead_id)
    if activity_type:
        activity_stmt = activity_stmt.where(LeadActivity.type == activity_type)

    activity_stmt = activity_stmt.order_by(desc(LeadActivity.created_at)).offset(offset).limit(limit)
    res = await db.execute(activity_stmt)
    return res.scalars().all()