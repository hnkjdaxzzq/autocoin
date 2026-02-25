from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import logging

from autocoin.config import settings
from autocoin.database import init_db
from autocoin.routers import transactions, imports, statistics, auth

logger = logging.getLogger("autocoin")


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Prevent browser caching of local static files during development."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/js/") or path.startswith("/css/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="Autocoin",
        description="Personal accounting application",
        version="0.1.0",
    )

    # Return first Pydantic validation error as readable detail string
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        for err in exc.errors():
            msg = err.get("msg", "")
            # Pydantic v2 wraps custom ValueError as "Value error, <msg>"
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, "):]
            if msg:
                return JSONResponse(
                    status_code=422, content={"detail": msg}
                )
        return JSONResponse(
            status_code=422, content={"detail": "请求参数不合法"}
        )

    # CORS - allow all origins for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prevent browser caching of static JS/CSS files
    app.add_middleware(NoCacheStaticMiddleware)

    @app.on_event("startup")
    def startup():
        init_db()
        # Security warnings
        if settings.jwt_secret == "autocoin-dev-secret-change-in-production":
            logger.warning(
                "\n" + "=" * 60
                + "\n  WARNING: 使用默认 JWT 密钥，请设置环境变量"
                + "\n  AUTOCOIN_JWT_SECRET=<你的随机密钥>"
                + "\n" + "=" * 60
            )
        if "*" in settings.cors_origins:
            logger.warning("CORS 允许所有来源 (*)，生产环境请设置具体域名")

    # IMPORTANT: Register API routes BEFORE static files mount
    # to prevent /api/v1/* from being served as static files
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(transactions.router, prefix=settings.api_prefix)
    app.include_router(imports.router, prefix=settings.api_prefix)
    app.include_router(statistics.router, prefix=settings.api_prefix)

    # Serve frontend SPA - must be last
    app.mount(
        "/",
        StaticFiles(directory=settings.frontend_dir, html=True),
        name="frontend",
    )

    return app
