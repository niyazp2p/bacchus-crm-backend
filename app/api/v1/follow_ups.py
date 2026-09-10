import uuid
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User, RoleType
from app.models.lead import Lead
from app.models.follow_up import FollowUp, FollowUpStatus
from app.models.activity import LeadActivity, ActivityType
from app.schemas.follow_up import FollowUpCreate, FollowUpUpdate, FollowUpResponse

router = APIRouter(prefix="/follow-ups", tags=["Follow-Ups"])

@router.post("", response_model=FollowUpResponse, status_code=status.HTTP_201_CREATED)
async def schedule_follow_up(
    payload: FollowUpCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    # Verify target lead exists
    stmt = select(Lead).where(Lead.id == payload.lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target lead not found.")

    if current_user.role == RoleType.TERRITORY_REP and lead.assigned_to_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot schedule follow-up on unassigned lead.")

    # Normalize incoming datetime to timezone-naive UTC for PostgreSQL DateTime columns
    scheduled_dt = payload.scheduled_at
    if scheduled_dt.tzinfo is not None:
        scheduled_dt = scheduled_dt.astimezone(timezone.utc).replace(tzinfo=None)

    follow_up = FollowUp(
        lead_id=payload.lead_id,
        user_id=current_user.id,
        scheduled_at=scheduled_dt,
        type=payload.type,
        status=FollowUpStatus.PENDING,
        notes=payload.notes,
    )
    db.add(follow_up)
    await db.flush()

    # Log schedule action to lead timeline
    activity = LeadActivity(
        lead_id=payload.lead_id,
        user_id=current_user.id,
        type=ActivityType.NOTE,
        meta_data={
            "action": "Follow-Up Scheduled",
            "follow_up_id": str(follow_up.id),
            "follow_up_type": payload.type.value,
            "scheduled_at": scheduled_dt.isoformat(),
        },
    )
    db.add(activity)
    await db.commit()
    await db.refresh(follow_up)
    return follow_up

@router.get("", response_model=list[FollowUpResponse])
async def list_follow_ups(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    lead_id: uuid.UUID | None = Query(None),
    follow_up_status: FollowUpStatus | None = Query(None, alias="status"),
    overdue_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(FollowUp)

    if current_user.role == RoleType.TERRITORY_REP:
        stmt = stmt.where(FollowUp.user_id == current_user.id)

    if lead_id:
        stmt = stmt.where(FollowUp.lead_id == lead_id)
    if follow_up_status:
        stmt = stmt.where(FollowUp.status == follow_up_status)
    if overdue_only:
        stmt = stmt.where(
            FollowUp.status == FollowUpStatus.PENDING,
            FollowUp.scheduled_at < datetime.utcnow()
        )

    stmt = stmt.order_by(FollowUp.scheduled_at.asc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.patch("/{follow_up_id}", response_model=FollowUpResponse)
async def update_follow_up(
    follow_up_id: uuid.UUID,
    payload: FollowUpUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    stmt = select(FollowUp).where(FollowUp.id == follow_up_id)
    result = await db.execute(stmt)
    follow_up = result.scalar_one_or_none()

    if not follow_up:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up record not found.")

    if current_user.role == RoleType.TERRITORY_REP and follow_up.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this follow-up.")

    update_dict = payload.model_dump(exclude_unset=True)

    if "scheduled_at" in update_dict and update_dict["scheduled_at"] is not None:
        dt = update_dict["scheduled_at"]
        if dt.tzinfo is not None:
            update_dict["scheduled_at"] = dt.astimezone(timezone.utc).replace(tzinfo=None)

    if update_dict.get("status") == FollowUpStatus.COMPLETED and follow_up.status != FollowUpStatus.COMPLETED:
        follow_up.completed_at = datetime.utcnow()

    for key, value in update_dict.items():
        setattr(follow_up, key, value)

    await db.commit()
    await db.refresh(follow_up)
    return follow_up