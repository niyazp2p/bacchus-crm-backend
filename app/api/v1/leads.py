import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user, require_roles
from app.models.user import User, RoleType
from app.models.lead import Lead, LeadStatus, LeadTier, CommercialModel
from app.models.activity import LeadActivity, ActivityType
from app.models.follow_up import FollowUp
from app.models.customer import Conversion
from app.schemas.lead import LeadCreate, LeadUpdate, LeadResponse
from app.services.lead_scoring import calculate_lead_score

router = APIRouter(prefix="/leads", tags=["Leads"])

async def generate_lead_code(db: AsyncSession) -> str:
    stmt = select(func.count(Lead.id))
    result = await db.execute(stmt)
    count = (result.scalar() or 0) + 1
    return f"BAC-LD-{count:05d}"

@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    score, tier = calculate_lead_score(
        commercial_model=payload.commercial_model,
        volume_estimate=payload.volume_estimate,
        country=payload.country,
        phone=payload.phone,
        email=payload.email,
    )
    lead_code = await generate_lead_code(db)

    lead = Lead(
        lead_code=lead_code,
        company_name=payload.company_name,
        contact_name=payload.contact_name,
        email=payload.email,
        phone=payload.phone,
        country=payload.country,
        state=payload.state,
        commercial_model=payload.commercial_model,
        volume_estimate=payload.volume_estimate,
        score=score,
        tier=tier,
        status=LeadStatus.NEW,
        assigned_to_id=current_user.id if current_user.role == RoleType.TERRITORY_REP else None,
    )
    db.add(lead)
    await db.flush()

    # Log Creation Activity
    activity = LeadActivity(
        lead_id=lead.id,
        user_id=current_user.id,
        type=ActivityType.NOTE,
        meta_data={
            "action": "Lead ingestion via CRM API",
            "initial_score": score,
            "tier": tier.value,
            "phone_registered": payload.phone,
        },
    )
    db.add(activity)
    await db.commit()
    await db.refresh(lead)
    return lead

@router.get("", response_model=list[LeadResponse])
async def list_leads(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    tier: LeadTier | None = Query(None),
    lead_status: LeadStatus | None = Query(None, alias="status"),
    commercial_model: CommercialModel | None = Query(None),
    country: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Lead)

    # Territory Representatives see only their assigned portfolio
    if current_user.role == RoleType.TERRITORY_REP:
        stmt = stmt.where(Lead.assigned_to_id == current_user.id)

    if tier:
        stmt = stmt.where(Lead.tier == tier)
    if lead_status:
        stmt = stmt.where(Lead.status == lead_status)
    if commercial_model:
        stmt = stmt.where(Lead.commercial_model == commercial_model)
    if country:
        stmt = stmt.where(Lead.country.ilike(f"%{country}%"))

    stmt = stmt.order_by(desc(Lead.created_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    stmt = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")

    if current_user.role == RoleType.TERRITORY_REP and lead.assigned_to_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this lead portfolio.")

    return lead

@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    stmt = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")

    update_dict = payload.model_dump(exclude_unset=True)

    # Validate assignment role permission
    if "assigned_to_id" in update_dict and update_dict["assigned_to_id"] != lead.assigned_to_id:
        if current_user.role not in [RoleType.SUPER_ADMIN, RoleType.SALES_DIRECTOR]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Directors or Admins can reassign lead accounts.",
            )
        activity = LeadActivity(
            lead_id=lead.id,
            user_id=current_user.id,
            type=ActivityType.ASSIGNMENT,
            meta_data={"assigned_to": str(update_dict["assigned_to_id"])},
        )
        db.add(activity)

    # Recalculate score if commercial factors change
    score_recalc_needed = any(k in update_dict for k in ["commercial_model", "volume_estimate", "country", "phone", "email"])
    
    for field, val in update_dict.items():
        setattr(lead, field, val)

    if score_recalc_needed:
        lead.score, lead.tier = calculate_lead_score(
            commercial_model=lead.commercial_model,
            volume_estimate=lead.volume_estimate,
            country=lead.country,
            phone=lead.phone,
            email=lead.email,
        )

    await db.commit()
    await db.refresh(lead)
    return lead

@router.delete("/{lead_id}", status_code=status.HTTP_200_OK, summary="Delete lead inquiry")
async def delete_lead(
    lead_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    # 1. Fetch Lead
    stmt = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead record not found in system ledger.",
        )

    # Check RBAC permissions
    if current_user.role == RoleType.TERRITORY_REP and lead.assigned_to_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot delete lead outside your territory portfolio.",
        )

    # 2. Check if converted (prevent foreign key break in conversions/customers table)
    conv_stmt = select(Conversion).where(Conversion.lead_id == lead_id)
    conversion = (await db.execute(conv_stmt)).scalar_one_or_none()
    if conversion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete lead that has already been converted to an institutional customer account.",
        )

    # 3. Clean up related child activities to ensure database integrity
    act_stmt = select(LeadActivity).where(LeadActivity.lead_id == lead_id)
    activities = (await db.execute(act_stmt)).scalars().all()
    for act in activities:
        await db.delete(act)

    # 4. Clean up related follow-ups
    fu_stmt = select(FollowUp).where(FollowUp.lead_id == lead_id)
    follow_ups = (await db.execute(fu_stmt)).scalars().all()
    for fu in follow_ups:
        await db.delete(fu)

    # 5. Expunge Lead
    lead_code = lead.lead_code
    company_name = lead.company_name
    await db.delete(lead)
    await db.commit()

    return {
        "status": "success",
        "message": f"Inquiry '{company_name}' ({lead_code}) expunged from operations ledger.",
        "id": str(lead_id),
    }