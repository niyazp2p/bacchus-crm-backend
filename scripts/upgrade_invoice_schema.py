import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import asyncio
from sqlalchemy import text
from app.core.database import engine
import app.models  # Ensures Base and metadata are loaded

async def upgrade_schema():
    print("\n--- Synchronizing Invoicing Schema with PostgreSQL ---")
    async with engine.begin() as conn:
        # Drop legacy invoice structure safely
        await conn.execute(text("DROP TABLE IF EXISTS invoice_items CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS invoices CASCADE;"))
        print("[OK] Dropped legacy invoice tables.")

        # Recreate tables with all new GST and bilateral dispatch columns
        await conn.run_sync(app.models.Base.metadata.create_all)
        print("[OK] Recreated 'invoices' and 'invoice_items' with complete schema.")

if __name__ == "__main__":
    asyncio.run(upgrade_schema())