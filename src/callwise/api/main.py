"""FastAPI application entrypoint: CORS, security headers, routers, and health checks."""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from callwise.api.auth import router as auth_router
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

    # Routers
    app.include_router(auth_router)

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
