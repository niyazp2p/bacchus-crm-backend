import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user, require_roles
from app.models.user import User, RoleType
from app.models.customer import Customer
from app.models.product import Product
from app.models.invoice import Invoice, InvoiceItem, PaymentStatus
from app.schemas.invoice import InvoiceCreate, InvoiceResponse, InvoiceStatusUpdate

router = APIRouter(prefix="/invoices", tags=["Invoicing & SKU Billing Engine"])

# Fixed Corporate Bureau Dispatcher Defaults
DEFAULT_BILLED_BY = {
    "name": "Bacchus World Spirits Limited",
    "address": "B 28 Manaar Tower, Sector 132, Noida, Uttar Pradesh 201304, India",
    "gstin": "09AAACB1234F1Z8",
    "pan": "AAACB1234F",
    "email": "admin@bacchusspiritsglobal.com",
    "phone": "+91 120 466 4253",
}

oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def round_curr(val: Decimal) -> Decimal:
    """Rounds values to two decimal currency places safely."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

async def generate_invoice_number(db: AsyncSession) -> str:
    """Generates sequential commercial invoice identifiers: BAC-INV-YYYY-XXXXX."""
    current_year = datetime.utcnow().year
    stmt = select(func.count(Invoice.id))
    result = await db.execute(stmt)
    count = (result.scalar() or 0) + 1
    return f"BAC-INV-{current_year}-{count:05d}"

async def get_pdf_dispatch_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    header_token: Annotated[str | None, Depends(oauth2_scheme_optional)] = None,
    query_token: str | None = Query(None, alias="token"),
) -> User:
    """
    Permits authentication via standard Bearer Authorization header
    OR ?token= query parameter to facilitate direct browser tab opening and printing.
    """
    token = header_token or query_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide Authorization header or ?token= query parameter.",
        )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials.")

    stmt = select(User).where(User.id == uuid.UUID(user_id))
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found.")
    return user

@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN, RoleType.SALES_DIRECTOR, RoleType.FINANCE_OFFICER]))],
):
    # 1. Verify Target Customer Entity
    cust_stmt = select(Customer).where(Customer.id == payload.customer_id)
    cust_res = await db.execute(cust_stmt)
    customer = cust_res.scalar_one_or_none()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Customer with ID {payload.customer_id} does not exist."
        )

    inv_number = await generate_invoice_number(db)
    
    # 2. Iterate and Compute Itemized SKU Billing
    running_subtotal = Decimal("0.00")
    running_igst = Decimal("0.00")
    invoice_items: list[InvoiceItem] = []

    for item_data in payload.items:
        sku_clean = item_data.sku_code.strip().upper()
        
        # Pull product defaults from database catalog
        prod_stmt = select(Product).where(Product.sku_code == sku_clean)
        prod = (await db.execute(prod_stmt)).scalar_one_or_none()

        # Fallback cascade: payload value -> master catalog value -> hardcoded default
        description = item_data.description or (prod.name if prod else sku_clean)
        unit = item_data.unit or (prod.unit if prod else "Cases")
        
        rate = item_data.rate
        if rate is None:
            if prod and prod.base_rate:
                rate = prod.base_rate
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Rate not provided for SKU '{sku_clean}' and no catalog default found.",
                )
        
        gst_percent = item_data.gst_percent
        if gst_percent is None:
            gst_percent = prod.default_gst_percent if prod else Decimal("18.00")

        # Mathematical Execution:
        # Amount = Quantity * Rate
        amount = round_curr(Decimal(item_data.quantity) * rate)
        # IGST = Amount * (GST% / 100)
        igst = round_curr(amount * (gst_percent / Decimal("100.00")))
        # Line Total = Amount + IGST
        line_total = round_curr(amount + igst)

        running_subtotal += amount
        running_igst += igst

        invoice_items.append(
            InvoiceItem(
                sku_code=sku_clean,
                description=description,
                unit=unit,
                quantity=item_data.quantity,
                rate=rate,
                amount=amount,
                gst_percent=gst_percent,
                igst_amount=igst,
                line_total=line_total,
            )
        )

    # Consignment Grand Total
    total_amount = running_subtotal + running_igst

    # 3. Normalize Timestamps for Database
    due_dt = payload.due_date
    if due_dt.tzinfo is not None:
        due_dt = due_dt.astimezone(timezone.utc).replace(tzinfo=None)

    billed_by_data = payload.billed_by.model_dump() if payload.billed_by else DEFAULT_BILLED_BY

    # 4. Construct Invoice Record
    invoice = Invoice(
        invoice_number=inv_number,
        customer_id=payload.customer_id,
        currency=payload.currency.upper(),
        subtotal=running_subtotal,
        tax_amount=running_igst,
        total_amount=total_amount,
        status=PaymentStatus.ISSUED,
        due_date=due_dt,
        supply_country=payload.supply_country,
        place_of_supply=payload.place_of_supply,
        billed_by_snapshot=billed_by_data,
        billed_to_snapshot=payload.billed_to.model_dump(),
        notes=payload.notes,
        items=invoice_items,
    )

    db.add(invoice)
    await db.commit()

    # Query with child relationship eager loaded
    fetch_stmt = (
        select(Invoice)
        .where(Invoice.id == invoice.id)
        .options(selectinload(Invoice.items))
    )
    result = await db.execute(fetch_stmt)
    return result.scalar_one()

@router.get("", response_model=list[InvoiceResponse])
async def list_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    customer_id: uuid.UUID | None = Query(None),
    status: PaymentStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(Invoice).options(selectinload(Invoice.items))

    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if status:
        stmt = stmt.where(Invoice.status == status)

    stmt = stmt.order_by(desc(Invoice.created_at)).offset(offset).limit(limit)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    stmt = select(Invoice).where(Invoice.id == invoice_id).options(selectinload(Invoice.items))
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice record not found.")
    return invoice

@router.patch("/{invoice_id}/status", response_model=InvoiceResponse)
async def update_invoice_status(
    invoice_id: uuid.UUID,
    payload: InvoiceStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN, RoleType.FINANCE_OFFICER]))],
):
    stmt = select(Invoice).where(Invoice.id == invoice_id).options(selectinload(Invoice.items))
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice record not found.")

    invoice.status = payload.status
    await db.commit()
    await db.refresh(invoice)
    return invoice

@router.delete("/{invoice_id}", status_code=status.HTTP_200_OK)
async def void_or_delete_invoice(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN]))],
    permanent: bool = Query(False, description="If true, permanently removes; otherwise marks as VOID"),
):
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice record not found.")

    if permanent:
        await db.delete(invoice)
        await db.commit()
        return {"status": "success", "message": f"Invoice {invoice.invoice_number} permanently expunged."}
    else:
        invoice.status = PaymentStatus.VOID
        await db.commit()
        return {"status": "success", "message": f"Invoice {invoice.invoice_number} marked as VOID."}

@router.get("/{invoice_id}/dispatch-pdf", summary="Render Institutional Printable HTML / PDF Dispatch Receipt")
async def render_dispatch_document(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_pdf_dispatch_user)],
):
    stmt = select(Invoice).where(Invoice.id == invoice_id).options(selectinload(Invoice.items))
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice record not found.")

    seller = inv.billed_by_snapshot
    buyer = inv.billed_to_snapshot

    # Build Rows
    table_rows = ""
    for idx, item in enumerate(inv.items, 1):
        table_rows += f"""
        <tr>
            <td style="border: 1px solid #dcdad5; padding: 10px; text-align: center;">{idx}</td>
            <td style="border: 1px solid #dcdad5; padding: 10px;">
                <strong style="color: #14120E;">{item.sku_code}</strong><br/>
                <span style="color: #666; font-size: 11px;">{item.description}</span>
            </td>
            <td style="border: 1px solid #dcdad5; padding: 10px; text-align: center;">{item.unit}</td>
            <td style="border: 1px solid #dcdad5; padding: 10px; text-align: right;">{item.quantity:,}</td>
            <td style="border: 1px solid #dcdad5; padding: 10px; text-align: right;">{inv.currency} {item.rate:,.2f}</td>
            <td style="border: 1px solid #dcdad5; padding: 10px; text-align: right;">{inv.currency} {item.amount:,.2f}</td>
            <td style="border: 1px solid #dcdad5; padding: 10px; text-align: center;">{item.gst_percent:.2f}%</td>
            <td style="border: 1px solid #dcdad5; padding: 10px; text-align: right; color: #8E7626;">{inv.currency} {item.igst_amount:,.2f}</td>
            <td style="border: 1px solid #dcdad5; padding: 10px; text-align: right; font-weight: bold;">{inv.currency} {item.line_total:,.2f}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8"/>
        <title>Dispatch Invoice - {inv.invoice_number}</title>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #14120E; margin: 36px; line-height: 1.4; }}
            .header-table, .details-table, .items-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            .crest {{ color: #8E7626; font-size: 20px; font-weight: bold; text-transform: uppercase; letter-spacing: 2px; }}
            .title {{ font-size: 26px; font-weight: bold; text-align: right; color: #14120E; }}
            .section-bar {{ background-color: #FAF7F2; padding: 8px 10px; border-left: 4px solid #8E7626; font-weight: bold; font-size: 11px; margin-bottom: 8px; letter-spacing: 1px; }}
            @media print {{
                body {{ margin: 0; }}
            }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="vertical-align: top;">
                    <div class="crest">Bacchus World Spirits Limited</div>
                    <div style="font-size: 12px; color: #555;">Institutional Distilling, State-Excise &amp; Global Export Corridors</div>
                </td>
                <td class="title">
                    COMMERCIAL TAX INVOICE<br/>
                    <span style="font-size: 14px; font-weight: normal; color: #666;">No: {inv.invoice_number}</span><br/>
                    <span style="font-size: 11px; font-weight: normal; color: #888;">Issue Date: {inv.issued_date.strftime('%d-%b-%Y')} | Due Date: {inv.due_date.strftime('%d-%b-%Y')}</span>
                </td>
            </tr>
        </table>

        <table class="details-table" style="font-size: 12px; margin-top: 10px;">
            <tr>
                <td style="width: 50%; vertical-align: top; padding-right: 15px;">
                    <div class="section-bar">BILLED BY (SUPPLIER / EXPORTER)</div>
                    <strong>{seller.get('name')}</strong><br/>
                    {seller.get('address')}<br/>
                    <strong>GSTIN:</strong> {seller.get('gstin')} | <strong>PAN:</strong> {seller.get('pan')}<br/>
                    <strong>Email:</strong> {seller.get('email')} | <strong>Phone:</strong> {seller.get('phone')}
                </td>
                <td style="width: 50%; vertical-align: top; padding-left: 15px;">
                    <div class="section-bar">BILLED TO (BUYER / CONSIGNEE)</div>
                    <strong>{buyer.get('name')}</strong><br/>
                    {buyer.get('address')}<br/>
                    <strong>GSTIN:</strong> {buyer.get('gstin')} | <strong>PAN:</strong> {buyer.get('pan')}<br/>
                    <strong>Country of Supply:</strong> {inv.supply_country} | <strong>Place of Supply:</strong> {inv.place_of_supply}<br/>
                    <strong>Email:</strong> {buyer.get('email')} | <strong>Phone:</strong> {buyer.get('phone')}
                </td>
            </tr>
        </table>

        <table class="items-table" style="font-size: 11px; margin-top: 15px;">
            <thead>
                <tr style="background-color: #14120E; color: #FAF7F2;">
                    <th style="padding: 10px; border: 1px solid #14120E;">#</th>
                    <th style="padding: 10px; border: 1px solid #14120E; text-align: left;">SKU Code &amp; Description</th>
                    <th style="padding: 10px; border: 1px solid #14120E;">Unit</th>
                    <th style="padding: 10px; border: 1px solid #14120E; text-align: right;">Quantity</th>
                    <th style="padding: 10px; border: 1px solid #14120E; text-align: right;">Unit Rate</th>
                    <th style="padding: 10px; border: 1px solid #14120E; text-align: right;">Amount (Txn Value)</th>
                    <th style="padding: 10px; border: 1px solid #14120E;">GST %</th>
                    <th style="padding: 10px; border: 1px solid #14120E; text-align: right;">IGST Tax</th>
                    <th style="padding: 10px; border: 1px solid #14120E; text-align: right;">Total Amount</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>

        <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 15px;">
            <tr>
                <td style="width: 55%; vertical-align: top; color: #555; font-size: 11px; padding-right: 20px;">
                    <div style="font-weight: bold; color: #14120E; margin-bottom: 4px;">Consignment Notes &amp; Statutory Declarations:</div>
                    <div>{inv.notes or 'Standard bonded corridor consignment. Certified export clearance.'}</div>
                    <div style="margin-top: 8px;">
                        1. Goods supplied comply with applicable State Excise, HMRC, and FSSAI standards.<br/>
                        2. Reverse charge is not applicable on this commercial invoice.
                    </div>
                </td>
                <td style="width: 45%; vertical-align: top;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 6px; text-align: right; color: #555;">Subtotal (Taxable Value):</td>
                            <td style="padding: 6px; text-align: right; font-weight: bold;">{inv.currency} {inv.subtotal:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px; text-align: right; color: #555;">Integrated Tax (Total IGST):</td>
                            <td style="padding: 6px; text-align: right; font-weight: bold; color: #8E7626;">{inv.currency} {inv.tax_amount:,.2f}</td>
                        </tr>
                        <tr style="border-top: 2px solid #14120E; border-bottom: 2px solid #14120E; font-size: 14px;">
                            <td style="padding: 8px; text-align: right; font-weight: bold;">Consignment Total:</td>
                            <td style="padding: 8px; text-align: right; font-weight: bold; color: #14120E;">{inv.currency} {inv.total_amount:,.2f}</td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return Response(content=html, media_type="text/html")