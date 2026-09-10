import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.router import api_router
from app.middleware.audit import AuditLoggingMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
)

# 1. Audit Logging Middleware (runs inside CORS wrapper)
app.add_middleware(AuditLoggingMiddleware)

# 2. Extract and sanitize production CORS origins
cors_env = os.getenv("BACKEND_CORS_ORIGINS", "")
if cors_env.startswith("["):
    origins = json.loads(cors_env)
elif cors_env:
    origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
else:
    origins = [
        "https://www.bacchusdistilleryindia.com",
        "https://bacchusdistilleryindia.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

# 3. CORS Middleware (outermost layer so preflight headers attach to all responses)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": getattr(settings, "ENVIRONMENT", "development"),
    }