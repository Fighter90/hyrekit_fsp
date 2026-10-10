"""FastAPI application factory — точка входа."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.arena.router import router as arena_router
from app.auth.router import router as auth_router
from app.candidates.router import router as candidate_router
from app.catalog.router import router as catalog_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.limiter import limiter
from app.core.seed import run as seed_demo
from app.employers.router import router as employer_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle."""
    logger.info('Starting HyreKit API...')
    # Демо-аккаунты и банк кандидатов (выключается SEED_DEMO=false)
    settings = get_settings()
    if settings.seed_demo:
        try:
            await seed_demo()
        except Exception:
            logger.warning('Seed skipped (DB may not be ready)', exc_info=True)
    yield
    logger.info('Shutting down HyreKit API...')


def create_app() -> FastAPI:
    """Фабрика FastAPI-приложения."""
    settings = get_settings()

    # Swagger UI и OpenAPI открыты по умолчанию: жюри проверяет описание API (ТЗ 3.5)
    docs_url = '/docs' if settings.docs_enabled else None
    redoc_url = '/redoc' if settings.docs_enabled else None
    openapi_url = '/openapi.json' if settings.docs_enabled else None

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description='HyreKit: подбор ИТ-специалистов с верифицированным профилем ФСП',
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # --- Rate Limiting (SEC-005/ARCH-010/LIVE-012) ---
    if settings.environment in ('testing', 'test'):
        limiter.enabled = False
    storage_uri = 'memory://' if settings.environment in ('testing', 'test') else (settings.redis_url or 'memory://')
    limiter._storage_uri = storage_uri
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
        allow_headers=['Authorization', 'Content-Type', 'Accept', 'X-Request-ID'],
    )

    # --- Exception Handlers ---
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        """Обработчик кастомных ошибок → JSON."""
        content: dict[str, str | None] = {
            'error': exc.error_code,
            'message': exc.message,
        }
        if exc.detail:
            content['detail'] = exc.detail
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(Exception)
    async def general_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Обработчик необработанных исключений → 500."""
        logger.exception('Unhandled exception: %s', exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                'error': 'INTERNAL_ERROR',
                'message': 'Внутренняя ошибка сервера',
            },
        )

    # --- Routers ---
    api_prefix = settings.api_v1_prefix

    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(catalog_router, prefix=api_prefix)
    app.include_router(candidate_router, prefix=api_prefix)
    app.include_router(employer_router, prefix=api_prefix)
    app.include_router(arena_router, prefix=api_prefix)

    # --- Static files: uploads (avatars, etc.) ---
    from pathlib import Path

    from starlette.staticfiles import StaticFiles

    uploads_dir = Path(settings.upload_dir).resolve()
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount(f'{api_prefix}/uploads', StaticFiles(directory=str(uploads_dir)), name='uploads')

    # --- Health Check (API-005/LIVE-015: доступен и с префиксом и без) ---
    @app.get('/health', tags=['system'], summary='Health Check')
    @app.get(f'{settings.api_v1_prefix}/health', tags=['system'], include_in_schema=False)
    async def health() -> dict[str, str]:
        return {'status': 'healthy', 'version': settings.app_version}

    # --- Logging ---
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    )

    return app


# Экземпляр приложения (для uvicorn)
app = create_app()
