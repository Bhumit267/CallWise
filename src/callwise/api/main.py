"""FastAPI application entrypoint: CORS, security headers, routers, and health checks."""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from callwise.api.analytics import router as analytics_router
from callwise.api.appointments import router as appointments_router
from callwise.api.audit_logs import router as audit_logs_router
from callwise.api.auth import router as auth_router
from callwise.api.calls import router as calls_router
from callwise.api.contacts import router as contacts_router
from callwise.api.follow_ups import router as follow_ups_router
from callwise.api.inbox import router as inbox_router
from callwise.api.knowledge import router as knowledge_router
from callwise.api.knowledge_misses import router as knowledge_misses_router
from callwise.api.messages import router as messages_router
from callwise.api.onboarding import router as onboarding_router
from callwise.api.phone_numbers import router as phone_numbers_router
from callwise.api.settings import router as settings_router
from callwise.api.team import router as team_router
from callwise.api.usage import router as usage_router
from callwise.api.widget import router as widget_router
from callwise.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforce standard HTTP defense-in-depth security headers."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Allow embedding for public widget routes; deny embedding for dashboard pages
        if not request.url.path.startswith("/api/widget/"):
            response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    app = FastAPI(
        title="Callwise API",
        version="0.1.0",
        description="Multi-tenant Voice AI Receptionist Dashboard API",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # Security Headers
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS configuration
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Authentication Router
    app.include_router(auth_router)

    # Core Read & Management Routers under /api
    app.include_router(settings_router, prefix="/api")
    app.include_router(knowledge_router, prefix="/api")
    app.include_router(calls_router, prefix="/api")
    app.include_router(messages_router, prefix="/api")
    app.include_router(appointments_router, prefix="/api")
    app.include_router(contacts_router, prefix="/api")
    app.include_router(follow_ups_router, prefix="/api")
    app.include_router(knowledge_misses_router, prefix="/api")
    app.include_router(inbox_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api")
    app.include_router(team_router, prefix="/api")
    app.include_router(audit_logs_router, prefix="/api")
    app.include_router(phone_numbers_router, prefix="/api")
    app.include_router(usage_router, prefix="/api")
    app.include_router(widget_router, prefix="/api")
    app.include_router(onboarding_router, prefix="/api")

    @app.get("/health", include_in_schema=False)
    @app.get("/api/health")
    async def health_check():
        from callwise.calls.killswitch import is_kill_switch_active
        from callwise.db.session import get_async_session
        from sqlalchemy import text

        db_ok = False
        try:
            async with get_async_session() as session:
                await session.execute(text("SELECT 1"))
                db_ok = True
        except Exception:
            db_ok = False

        return {
            "status": "ok" if db_ok else "degraded",
            "database": "connected" if db_ok else "unreachable",
            "kill_switch_active": is_kill_switch_active(),
            "version": "0.1.0",
        }

    return app


app = create_app()
