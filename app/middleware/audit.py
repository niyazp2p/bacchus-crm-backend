import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from jose import jwt, JWTError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXCLUDED_PATHS = {"/api/v1/auth/login", "/api/v1/docs", "/api/v1/openapi.json", "/api/v1/redoc"}

class AuditLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Pass read-only traffic and documentation requests straight through
        if request.method not in MUTATING_METHODS or any(request.url.path.startswith(p) for p in EXCLUDED_PATHS):
            return await call_next(request)

        start_time = time.perf_counter()
        response = await call_next(request)
        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Extract actor credentials from Authorization header if present
        auth_header = request.headers.get("authorization")
        user_id = None
        user_email = None
        user_role = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = uuid.UUID(payload.get("sub")) if payload.get("sub") else None
                user_email = payload.get("email")
                user_role = payload.get("role")
            except (JWTError, ValueError):
                pass

        # Capture Client IP
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
        user_agent = request.headers.get("user-agent", "")[:255]

        # Log asynchronously in detached DB session
        async def persist_audit_record():
            try:
                async with AsyncSessionLocal() as session:
                    log_entry = AuditLog(
                        user_id=user_id,
                        user_email=user_email,
                        user_role=user_role,
                        method=request.method,
                        endpoint=request.url.path,
                        status_code=response.status_code,
                        client_ip=client_ip,
                        user_agent=user_agent,
                        execution_time_ms=execution_time_ms,
                        meta_data={
                            "query_params": dict(request.query_params),
                            "client_port": request.client.port if request.client else None,
                        },
                    )
                    session.add(log_entry)
                    await session.commit()
            except Exception as exc:
                print(f"[ERROR] Audit logging failed: {exc}")

        # Fire and forget into background event loop
        import asyncio
        asyncio.create_task(persist_audit_record())

        return response