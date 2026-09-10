from fastapi import APIRouter
from app.api.v1 import (
    auth,
    profile,
    leads,
    follow_ups,
    activities,
    conversions,
    customers,
    products,
    invoices,
    audit_logs,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(leads.router)
api_router.include_router(follow_ups.router)
api_router.include_router(activities.router)
api_router.include_router(conversions.router)
api_router.include_router(customers.router)
api_router.include_router(products.router)
api_router.include_router(invoices.router)
api_router.include_router(audit_logs.router)