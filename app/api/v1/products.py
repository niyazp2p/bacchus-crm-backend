import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user, require_roles
from app.models.user import User, RoleType
from app.models.product import Product, ProductCategory
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse

router = APIRouter(prefix="/products", tags=["Product Catalog & SKUs"])

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN, RoleType.SALES_DIRECTOR]))],
):
    stmt = select(Product).where(Product.sku_code == payload.sku_code.upper())
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"SKU {payload.sku_code} already registered.")

    product = Product(
        sku_code=payload.sku_code.upper(),
        name=payload.name,
        category=payload.category,
        description=payload.description,
        unit=payload.unit,
        bottle_volume=payload.bottle_volume,
        bottles_per_case=payload.bottles_per_case,
        abv=payload.abv,
        base_rate=payload.base_rate,
        default_gst_percent=payload.default_gst_percent,
        is_active=payload.is_active,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product

@router.get("", response_model=list[ProductResponse])
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    category: ProductCategory | None = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(Product)
    if active_only:
        stmt = stmt.where(Product.is_active == True)
    if category:
        stmt = stmt.where(Product.category == category)

    stmt = stmt.order_by(desc(Product.created_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    stmt = select(Product).where(Product.id == product_id)
    product = (await db.execute(stmt)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product

@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN, RoleType.SALES_DIRECTOR]))],
):
    stmt = select(Product).where(Product.id == product_id)
    product = (await db.execute(stmt)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(product, field, val)

    await db.commit()
    await db.refresh(product)
    return product

@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_product(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([RoleType.SUPER_ADMIN]))],
    permanent: bool = Query(False, description="If false, performs soft delete by toggling is_active"),
):
    stmt = select(Product).where(Product.id == product_id)
    product = (await db.execute(stmt)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    if permanent:
        await db.delete(product)
        await db.commit()
        return {"status": "success", "message": f"Product {product.sku_code} permanently deleted."}
    else:
        product.is_active = False
        await db.commit()
        return {"status": "success", "message": f"Product {product.sku_code} marked as inactive (soft deleted)."}