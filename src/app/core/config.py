"""Конфигурация приложения через pydantic-settings."""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Настройки приложения. Все секреты загружаются из .env."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # --- Общие ---
    environment: str = 'development'
    debug: bool = False
    log_level: str = 'INFO'
    app_name: str = 'HyreKit'
    app_version: str = '0.1.0'
    api_v1_prefix: str = '/api/v1'

    # --- Database ---
    database_url: str = 'postgresql+asyncpg://hyrekit:devpassword@localhost:5432/hyrekit'
    database_echo: bool = False

    # --- Redis ---
    redis_url: str = 'redis://localhost:6379/0'

    # --- Auth / Security ---
    secret_key: str  # ОБЯЗАТЕЛЬНО из .env — нет default!
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # --- CORS ---
    cors_origins: list[str] = Field(
        default=['http://localhost:3000', 'http://localhost:8000'],
    )

    # --- LLM ---
    gigachat_credentials: str = ''
    gigachat_scope: str = 'GIGACHAT_API_PERS'
    gigachat_model: str = 'GigaChat'

    # --- Демо и публичный адрес ---
    seed_demo: bool = True  # демо-аккаунты и синтетический банк кандидатов при старте
    calibration_interval_minutes: int = 60  # мониторинг утечек заданий (FSP-33); 0 — выключен
    guest_mode: bool = True  # экспресс-тест для жюри без регистрации (FSP-32)
    public_url: str = 'http://localhost:3000'  # адрес фронтенда для ссылок в письмах
    docs_enabled: bool = True  # Swagger UI и /openapi.json (ТЗ 3.5: API описан через OpenAPI)

    # --- Почта (подтверждение адреса) ---
    smtp_host: str = ''  # пусто — письмо не отправляется, ссылка пишется в лог
    smtp_port: int = 1025
    smtp_user: str = ''
    smtp_password: str = ''
    smtp_tls: bool = False
    mail_from: str = 'HyreKit <noreply@hyrekit.ru>'

    # --- File Storage ---
    upload_dir: str = './uploads'
    max_file_size_mb: int = 10

    # --- QA/Admin ---
    qa_admin_api_key: str = ''

    @property
    def max_file_size_bytes(self) -> int:
        """Максимальный размер файла в байтах."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        """Проверка production-окружения."""
        return self.environment == 'production'

    # SEC-002: Валидация SECRET_KEY при запуске
    @model_validator(mode='after')
    def validate_secret_key(self) -> Settings:
        """Отказ запуска если SECRET_KEY содержит placeholder-значение."""
        weak_markers = ('change-me', 'change_me', 'placeholder', 'CHANGE', 'super-secret')
        if any(marker in self.secret_key.lower() for marker in weak_markers):
            if self.is_production:
                msg = (
                    'SECRET_KEY содержит placeholder-значение! '
                    'Сгенерируйте: python -c "import secrets; print(secrets.token_hex(64))"'
                )
                raise ValueError(msg)
            logger.warning(
                'SECRET_KEY содержит placeholder-значение. Не используйте его в production!',
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Фабрика настроек (кэшированная через lru_cache)."""
    return Settings()
