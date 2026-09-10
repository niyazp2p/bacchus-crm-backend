import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user, require_roles
from app.models.user import User, RoleType
from app.models.customer import Customer, Conversion
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse

from app.models.lead import Lead, LeadStatus
from app.models.activity import LeadActivity, ActivityType
from app.models.invoice import Invoice, PaymentStatus

router = APIRouter(prefix="/customers", tags=["Customers"])

@router.get("", response_model=list[CustomerResponse])
async def list_customers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    country: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(Customer)

    if current_user.role == RoleType.TERRITORY_REP:
        stmt = stmt.where(Customer.account_manager_id == current_user.id)

    if country:
        stmt = stmt.where(Customer.country.ilike(f"%{country}%"))

    stmt = stmt.order_by(desc(Customer.created_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    stmt = select(Customer).where(Customer.id == customer_id)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    if current_user.role == RoleType.TERRITORY_REP and customer.account_manager_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this institutional customer.")

    return customer

@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN, RoleType.SALES_DIRECTOR]))],
):
    stmt = select(Customer).where(Customer.id == customer_id)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    update_dict = payload.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(customer, k, v)

    await db.commit()
    await db.refresh(customer)
    return customer

@router.delete("/{customer_id}", status_code=status.HTTP_200_OK)
async def delete_customer_sequence(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN, RoleType.SALES_DIRECTOR]))],
):
    # 1. Fetch target customer
    stmt = select(Customer).where(Customer.id == customer_id)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer entity not found.",
        )

    # 2. Block deletion if customer has issued or paid invoices
    inv_stmt = select(Invoice).where(
        Invoice.customer_id == customer_id,
        Invoice.status.in_([PaymentStatus.ISSUED, PaymentStatus.PAID]),
    )
    active_invoices = (await db.execute(inv_stmt)).scalars().all()
    if active_invoices:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete customer with {len(active_invoices)} active or settled invoices. Archive customer or void invoices first.",
        )

    # 3. Locate linked Conversion record
    conv_stmt = select(Conversion).where(Conversion.customer_id == customer_id)
    conversion = (await db.execute(conv_stmt)).scalar_one_or_none()

    # 4. If linked to an original Lead, revert status and log timeline activity
    if conversion:
        lead_stmt = select(Lead).where(Lead.id == conversion.lead_id)
        lead = (await db.execute(lead_stmt)).scalar_one_or_none()

        if lead:
            lead.status = LeadStatus.NEGOTIATION
            
            reversion_activity = LeadActivity(
                lead_id=lead.id,
                user_id=current_user.id,
                type=ActivityType.STATUS_CHANGE,
                meta_data={
                    "action": "Customer Entity Deleted",
                    "previous_customer_code": customer.customer_code,
                    "reverted_lead_status": LeadStatus.NEGOTIATION.value,
                    "initiated_by": current_user.email,
                },
            )
            db.add(reversion_activity)

        # Remove the conversion record
        await db.delete(conversion)

    # 5. Delete the Customer entity
    deleted_code = customer.customer_code
    deleted_name = customer.company_name
    await db.delete(customer)

    await db.commit()

    return {
        "status": "success",
        "message": f"Customer '{deleted_name}' ({deleted_code}) successfully deleted. Associated lead reverted to NEGOTIATION.",
        "customer_id": str(customer_id),
    }