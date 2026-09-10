import sys
from pathlib import Path
from decimal import Decimal

# Add project root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import asyncio
import os
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.core.database import Base

# Explicitly import all declarative models so they register on Base.metadata
import app.models.user
import app.models.lead
import app.models.follow_up
import app.models.activity
import app.models.customer
import app.models.product
import app.models.invoice
import app.models.audit

# Clean connection URL for asyncpg / Neon compatibility
raw_db_url = os.getenv("DATABASE_URL") or settings.ASYNC_DATABASE_URL
if raw_db_url.startswith("postgresql://"):
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)

if "sslmode=require" in raw_db_url:
    raw_db_url = raw_db_url.replace("sslmode=require", "ssl=require")
if "&channel_binding=" in raw_db_url:
    raw_db_url = raw_db_url.split("&channel_binding=")[0]

# Dedicated engine for database provisioning
init_engine = create_async_engine(
    raw_db_url,
    echo=False,
    pool_pre_ping=True,
)

InitSessionLocal = async_sessionmaker(
    bind=init_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Official Bacchus Master Catalog Portfolio
BACCHUS_CATALOG = [
    {
        "sku_code": "TAL-12-750",
        "name": "Talsons' Reserve 12 Years Single Malt Whisky",
        "category": app.models.product.ProductCategory.SINGLE_MALT,
        "description": "Double wood matured single malt, 12 years cask aged in Punjab cellars.",
        "unit": "Cases",
        "bottle_volume": "750 ml",
        "bottles_per_case": 12,
        "abv": "42.8% V/V",
        "base_rate": Decimal("3500.00"),
        "default_gst_percent": Decimal("18.00"),
    },
    {
        "sku_code": "JC-WHISKY-750",
        "name": "Jackie's Crown Blended Scotch Style Whisky",
        "category": app.models.product.ProductCategory.BLENDED_WHISKY,
        "description": "Blended crafted malt with notes of toasted oak, honey, and spice.",
        "unit": "Cases",
        "bottle_volume": "750 ml",
        "bottles_per_case": 12,
        "abv": "42.8% V/V",
        "base_rate": Decimal("2200.00"),
        "default_gst_percent": Decimal("18.00"),
    },
    {
        "sku_code": "CB-WHISKY-750",
        "name": "Crazy Boxer Straight-Up Whisky",
        "category": app.models.product.ProductCategory.BLENDED_WHISKY,
        "description": "Bold character kinetic spirit delivering high-energy toasted sugar and raw cask warmth.",
        "unit": "Cases",
        "bottle_volume": "750 ml",
        "bottles_per_case": 12,
        "abv": "42.8% V/V",
        "base_rate": Decimal("1800.00"),
        "default_gst_percent": Decimal("18.00"),
    },
    {
        "sku_code": "ROZ-VODKA-750",
        "name": "Rozzita Artisanal Cold-Filtered Vodka",
        "category": app.models.product.ProductCategory.VODKA,
        "description": "Triple sub-zero cold-filtered grain neutral spirit across four botanical infusions.",
        "unit": "Cases",
        "bottle_volume": "750 ml",
        "bottles_per_case": 12,
        "abv": "40.0% V/V",
        "base_rate": Decimal("1600.00"),
        "default_gst_percent": Decimal("18.00"),
    },
    {
        "sku_code": "CB-RUM-XXX-750",
        "name": "Crazy Boxer XXX Dark Overproof Spiced Rum",
        "category": app.models.product.ProductCategory.RUM,
        "description": "Slow-fermented cane molasses aged in heavy charred oak staves.",
        "unit": "Cases",
        "bottle_volume": "750 ml",
        "bottles_per_case": 12,
        "abv": "42.8% V/V",
        "base_rate": Decimal("1750.00"),
        "default_gst_percent": Decimal("18.00"),
    },
]

def hash_password(password: str) -> str:
    """Safe hashing using native bcrypt with a 72-byte ceiling."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

async def build_tables_and_seed():
    print("\n--- Synchronizing Database Schema ---")
    async with init_engine.begin() as conn:
        # Create all registered tables if they do not exist
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] All PostgreSQL tables verified/created successfully.")

    async with InitSessionLocal() as session:
        # 1. Seed Initial Super Admin
        admin_stmt = select(app.models.user.User).where(app.models.user.User.email == settings.SUPERADMIN_EMAIL)
        admin_res = await session.execute(admin_stmt)
        admin = admin_res.scalar_one_or_none()

        if not admin:
            admin_user = app.models.user.User(
                name="Executive Desk",
                email=settings.SUPERADMIN_EMAIL,
                password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
                role=app.models.user.RoleType.SUPER_ADMIN,
                territory="Global HQ",
                is_active=True,
            )
            session.add(admin_user)
            await session.commit()
            print(f"[OK] Master Superadmin seeded: {settings.SUPERADMIN_EMAIL}")
        else:
            print(f"[INFO] Superadmin already exists: {settings.SUPERADMIN_EMAIL}")

        # 2. Seed Master SKU Product Catalog
        print("\n--- Seeding Master Product Catalog ---")
        seeded_count = 0
        for item in BACCHUS_CATALOG:
            prod_stmt = select(app.models.product.Product).where(app.models.product.Product.sku_code == item["sku_code"])
            existing_prod = (await session.execute(prod_stmt)).scalar_one_or_none()

            if not existing_prod:
                session.add(app.models.product.Product(**item))
                seeded_count += 1

        if seeded_count > 0:
            await session.commit()
            print(f"[OK] Seeded {seeded_count} new master catalog SKUs.")
        else:
            print("[INFO] All master catalog SKUs already exist in database.")

    await init_engine.dispose()
    print("\n=======================================================")
    print(">>> DATABASE INITIALIZATION & SEEDING COMPLETED <<<")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(build_tables_and_seed())