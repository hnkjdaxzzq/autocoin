from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from autocoin.config import settings
from autocoin.database import init_db
from autocoin.routers import transactions, imports, statistics


def create_app() -> FastAPI:
    app = FastAPI(
        title="Autocoin",
        description="Personal accounting application",
        version="0.1.0",
    )

    # CORS - allow all origins for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup():
        init_db()

    # IMPORTANT: Register API routes BEFORE static files mount
    # to prevent /api/v1/* from being served as static files
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
