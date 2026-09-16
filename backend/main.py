"""App factory, CORS, router mounting. Nothing else lives here."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import DomainError, domain_error_handler
from app.db.session import engine


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # SQLite (local dev, tests) creates tables directly. Postgres in
        # production is managed through Alembic migrations instead.
        if settings.database_url.startswith("sqlite"):
            SQLModel.metadata.create_all(engine)
        yield

    app = FastAPI(title="Resume Analyzer API", lifespan=lifespan)

    # Explicit allowlist from env, never "*": credentials are involved.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(api_router)

    return app


app = create_app()
