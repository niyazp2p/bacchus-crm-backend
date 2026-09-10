import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user, require_roles
from app.models.user import User, RoleType
from app.models.lead import Lead, LeadStatus
from app.models.customer import Customer, Conversion
from app.models.activity import LeadActivity, ActivityType
from app.schemas.customer import ConversionCreate, ConversionResponse

router = APIRouter(prefix="/conversions", tags=["Conversions"])

async def generate_customer_code(db: AsyncSession) -> str:
    stmt = select(func.count(Customer.id))
    result = await db.execute(stmt)
    count = (result.scalar() or 0) + 1
    return f"BAC-CUST-{count:05d}"

@router.post("", response_model=ConversionResponse, status_code=status.HTTP_201_CREATED)
async def convert_lead_to_customer(
    payload: ConversionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN, RoleType.SALES_DIRECTOR, RoleType.TERRITORY_REP]))],
):
    # 1. Fetch target Lead
    stmt = select(Lead).where(Lead.id == payload.lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target lead not found.")

    if current_user.role == RoleType.TERRITORY_REP and lead.assigned_to_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot convert lead assigned to another representative.")

    # 2. Prevent duplicate conversion
    check_conversion_stmt = select(Conversion).where(Conversion.lead_id == payload.lead_id)
    existing_conversion = (await db.execute(check_conversion_stmt)).scalar_one_or_none()
    if existing_conversion or lead.status == LeadStatus.CONVERTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This lead has already been converted into an institutional customer.",
        )

    # 3. Create Institutional Customer Account
    cust_code = await generate_customer_code(db)
    account_manager = lead.assigned_to_id if lead.assigned_to_id else current_user.id

    customer = Customer(
        customer_code=cust_code,
        company_name=lead.company_name,
        tax_identifier=payload.tax_identifier,
        country=lead.country,
        account_manager_id=account_manager,
    )
    db.add(customer)
    await db.flush()

    # 4. Create Conversion Link
    conversion = Conversion(
        lead_id=lead.id,
        customer_id=customer.id,
        deal_value=payload.deal_value,
        commercial_model=payload.commercial_model,
    )
    db.add(conversion)

    # 5. Mutate Lead status to CONVERTED
    lead.status = LeadStatus.CONVERTED

    # 6. Append timeline milestone activity
    activity = LeadActivity(
        lead_id=lead.id,
        user_id=current_user.id,
        type=ActivityType.STATUS_CHANGE,
        meta_data={
            "action": "Lead Converted to Customer",
            "customer_id": str(customer.id),
            "customer_code": customer.customer_code,
            "deal_value": str(payload.deal_value),
            "commercial_model": payload.commercial_model.value,
        },
    )
    db.add(activity)

    await db.commit()
    await db.refresh(conversion)
    await db.refresh(customer)

    return ConversionResponse(
        id=conversion.id,
        lead_id=conversion.lead_id,
        customer_id=conversion.customer_id,
        deal_value=conversion.deal_value,
        commercial_model=conversion.commercial_model,
        converted_at=conversion.converted_at,
        customer=customer,
    )

@router.get("", response_model=list[ConversionResponse])
async def list_conversions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    stmt = select(Conversion)
    result = await db.execute(stmt)
    conversions = result.scalars().all()

    response_items = []
    for conv in conversions:
        cust_stmt = select(Customer).where(Customer.id == conv.customer_id)
        cust = (await db.execute(cust_stmt)).scalar_one()
        response_items.append(
            ConversionResponse(
                id=conv.id,
                lead_id=conv.lead_id,
                customer_id=conv.customer_id,
                deal_value=conv.deal_value,
                commercial_model=conv.commercial_model,
                converted_at=conv.converted_at,
                customer=cust,
            )
        )
    return response_items