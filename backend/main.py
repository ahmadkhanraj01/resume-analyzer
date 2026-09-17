"""App factory, CORS, router mounting. Nothing else lives here."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import DomainError, domain_error_handler, request_validation_handler
from app.db.session import engine, sync_sqlite_schema
from app.services import scoring


def create_app() -> FastAPI:
    settings = get_settings()
    # Uvicorn configures its own loggers only; without this the app's
    # per-stage timing lines never reach stdout.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # SQLite (local dev, tests) creates tables directly. Postgres in
        # production is managed through Alembic migrations instead.
        if settings.database_url.startswith("sqlite"):
            sync_sqlite_schema(engine)
        # Load the embedding model now so the first analysis after a cold
        # start does not pay for it on top of Render's own wake-up time.
        await run_in_threadpool(scoring._model)
        yield

    app = FastAPI(title="Resume Analyzer API", lifespan=lifespan)

    # Explicit allowlist from env, never "*". Auth is a bearer header, not a
    # cookie, so credentials mode is not needed and stays off.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.include_router(api_router)

    return app


app = create_app()
