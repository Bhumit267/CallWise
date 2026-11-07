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
from callwise.api.settings import router as settings_router
from callwise.api.team import router as team_router
from callwise.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforce standard HTTP defense-in-depth security headers."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
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
    app.include_router(onboarding_router, prefix="/api")

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
