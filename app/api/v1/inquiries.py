from datetime import datetime
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.lead import Lead, LeadStatus, LeadTier, CommercialModel
from app.models.activity import LeadActivity, ActivityType
from app.schemas.inquiry import ContactInquiryPayload, ContactInquiryResponse

router = APIRouter(prefix="/inquiries", tags=["Public Inquiries"])

CATEGORY_MAPPING = {
    "General Corporate Inquiries": CommercialModel.DISTRIBUTION,
    "Global Distribution Partnership": CommercialModel.DISTRIBUTION,
    "Private Label & Turnkey Distillation": CommercialModel.PRIVATE_LABEL,
    "Institutional Spirit Allocation": CommercialModel.STATE_OWNERSHIP,
}

async def generate_lead_code(db: AsyncSession) -> str:
    stmt = select(func.count(Lead.id))
    result = await db.execute(stmt)
    count = (result.scalar() or 0) + 1
    return f"BAC-LD-{count:05d}"

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
    model = CATEGORY_MAPPING.get(payload.category, CommercialModel.DISTRIBUTION)
    lead_code = await generate_lead_code(db)

    # Automated scoring rules
    is_high_volume = payload.category in [
        "Global Distribution Partnership",
        "Institutional Spirit Allocation"
    ]
    computed_score = 65 if is_high_volume else 40
    computed_tier = LeadTier.WARM if is_high_volume else LeadTier.COLD

    new_lead = Lead(
        lead_code=lead_code,
        company_name=payload.name.strip(),
        contact_name=payload.name.strip(),
        email=payload.email.strip().lower(),
        phone=None,
        country="India",
        state=None,
        commercial_model=model,
        volume_estimate=payload.message[:250],
        score=computed_score,
        tier=computed_tier,
        status=LeadStatus.NEW,
    )
    db.add(new_lead)
    await db.flush()

    # Log full initial message to the lead activity timeline
    activity = LeadActivity(
        lead_id=new_lead.id,
        user_id=None,
        type=ActivityType.NOTE,
        meta_data={
            "source": "WEBSITE_CONTACT_LEDGER",
            "category_selected": payload.category,
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