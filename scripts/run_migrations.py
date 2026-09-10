import sys
from pathlib import Path
from alembic.config import Config
from alembic import command

# Add root directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings

def apply_migrations():
    print("[INFO] Applying Alembic database migrations to production...")
    alembic_cfg = Config(str(BASE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.ASYNC_DATABASE_URL)
    
    # Upgrade database schema to latest head
    command.upgrade(alembic_cfg, "head")
    print("[OK] Migrations successfully applied.")

if __name__ == "__main__":
    apply_migrations()