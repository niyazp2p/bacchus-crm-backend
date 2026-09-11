import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.lead import Lead, LeadStatus, LeadTier, CommercialModel
from app.models.activity import LeadActivity, ActivityType
from app.models.user import User
from app.schemas.inquiry import ContactInquiryPayload, ContactInquiryResponse

router = APIRouter(prefix="/inquiries", tags=["Public Inquiries"])

CATEGORY_MAP = {
    "General Corporate Inquiries": CommercialModel.DISTRIBUTION,
    "Global Distribution Partnership": CommercialModel.DISTRIBUTION,
    "Private Label & Turnkey Distillation": CommercialModel.PRIVATE_LABEL,
    "Institutional Spirit Allocation": CommercialModel.STATE_OWNERSHIP,
}

async def generate_unique_lead_code(db: AsyncSession) -> str:
    stmt = select(func.count(Lead.id))
    result = await db.execute(stmt)
    count = (result.scalar() or 0) + 1
    suffix = uuid.uuid4().hex[:4].upper()
    return f"BAC-LD-{count:04d}-{suffix}"

@router.post(
    "/contact",
    response_model=ContactInquiryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit public contact inquiry"
)
async def submit_public_inquiry(
    payload: ContactInquiryPayload,
    db: AsyncSession = Depends(get_db)
):
    try:
        category_val = payload.category or "General Corporate Inquiries"
        model = CATEGORY_MAP.get(category_val, CommercialModel.DISTRIBUTION)
        lead_code = await generate_unique_lead_code(db)

        is_high_volume = category_val in [
            "Global Distribution Partnership",
            "Institutional Spirit Allocation"
        ]

        # 1. Ingest Lead Record with direct phone number
        new_lead = Lead(
            lead_code=lead_code,
            company_name=payload.name.strip(),
            contact_name=payload.name.strip(),
            email=str(payload.email).strip().lower(),
            phone=payload.phone.strip() if payload.phone else None,
            country="India",
            state=None,
            commercial_model=model,
            volume_estimate=(payload.message.strip())[:250],
            score=65 if is_high_volume else 40,
            tier=LeadTier.WARM if is_high_volume else LeadTier.COLD,
            status=LeadStatus.NEW,
        )
        db.add(new_lead)
        await db.flush()

        # 2. System user fallback for foreign key constraint
        user_stmt = select(User.id).order_by(User.created_at.asc()).limit(1)
        system_user_id = (await db.execute(user_stmt)).scalar_one_or_none()

        # 3. Log initial message activity
        if system_user_id:
            activity = LeadActivity(
                lead_id=new_lead.id,
                user_id=system_user_id,
                type=ActivityType.NOTE,
                meta_data={
                    "source": "WEBSITE_CONTACT_LEDGER",
                    "category_selected": category_val,
                    "phone": payload.phone.strip() if payload.phone else None,
                    "full_dispatch": payload.message.strip(),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            db.add(activity)

        await db.commit()

        return ContactInquiryResponse(
            success=True,
            reference_code=lead_code,
            message="Your dispatch has been registered in the institutional ledger.",
            received_at=datetime.utcnow()
        )

    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record inquiry dispatch: {str(exc)}"
        )