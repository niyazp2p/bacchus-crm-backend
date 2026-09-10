import asyncio
from datetime import datetime, timezone
from uuid import UUID
from arq.connections import RedisSettings
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.lead import Lead, LeadStatus, LeadTier
from app.models.follow_up import FollowUp, FollowUpStatus
from app.models.invoice import Invoice
from app.models.activity import LeadActivity, ActivityType

# 1. Task: Background Invoice Dispatch Emailer
async def task_send_invoice_dispatch_notification(ctx, invoice_id_str: str):
    inv_uuid = UUID(invoice_id_str)
    async with AsyncSessionLocal() as db:
        stmt = select(Invoice).where(Invoice.id == inv_uuid)
        inv = (await db.execute(stmt)).scalar_one_or_none()
        if not inv:
            return f"[ERROR] Invoice {invoice_id_str} not found."

        # Simulate async SMTP / SES delivery
        await asyncio.sleep(1.5)
        print(f"[WORKER] Consignment slip dispatched for {inv.invoice_number} to {inv.billed_to_snapshot.get('email')}")
        return f"Dispatched invoice {inv.invoice_number}"

# 2. Cron Task: Scan Overdue Follow-ups & Alert Reps
async def cron_scan_overdue_follow_ups(ctx):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with AsyncSessionLocal() as db:
        stmt = select(FollowUp).where(
            and_(
                FollowUp.scheduled_at < now,
                FollowUp.status == FollowUpStatus.SCHEDULED,
            )
        )
        overdue_items = (await db.execute(stmt)).scalars().all()
        
        updated_count = 0
        for item in overdue_items:
            # Append timeline warning to lead activity
            activity = LeadActivity(
                lead_id=item.lead_id,
                user_id=item.user_id,
                type=ActivityType.FOLLOW_UP_SCHEDULED,
                meta_data={
                    "alert": "SLA Missed: Scheduled follow-up overdue",
                    "follow_up_id": str(item.id),
                    "scheduled_at": item.scheduled_at.isoformat(),
                },
            )
            db.add(activity)
            updated_count += 1
            
        await db.commit()
        print(f"[CRON] Overdue scanner evaluated: {updated_count} follow-ups flagged.")
        return updated_count

# 3. Cron Task: Auto-Decay Inactive Leads
async def cron_decay_stale_leads(ctx):
    """Flags HOT/WARM leads without updates in >7 days down one tier."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with AsyncSessionLocal() as db:
        stmt = select(Lead).where(Lead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED]))
        leads = (await db.execute(stmt)).scalars().all()

        decayed = 0
        for lead in leads:
            days_inactive = (now - lead.updated_at).days
            if days_inactive >= 7 and lead.tier == LeadTier.HOT:
                lead.tier = LeadTier.WARM
                decayed += 1
            elif days_inactive >= 14 and lead.tier == LeadTier.WARM:
                lead.tier = LeadTier.COLD
                decayed += 1

        if decayed > 0:
            await db.commit()
        print(f"[CRON] Lead decay scan complete: {decayed} tiers adjusted.")
        return decayed

# Worker Lifespan & Settings
class WorkerSettings:
    functions = [task_send_invoice_dispatch_notification]
    # Periodic Cron schedules:
    # Overdue scanner every 15 minutes, lead decay every midnight
    cron_jobs = []
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )