"""Кастомные HTTP-исключения с единым JSON-форматом."""

from __future__ import annotations


class AppError(Exception):
    """Базовое исключение приложения."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        error_code: str = 'INTERNAL_ERROR',
        detail: str | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
        super().__init__(message)


# --- Auth ---
class InvalidCredentials(AppError):
    def __init__(self) -> None:
        super().__init__(
            message='Неверный email или пароль',
            status_code=401,
            error_code='INVALID_CREDENTIALS',
        )


class TokenExpired(AppError):
    def __init__(self) -> None:
        super().__init__(
            message='Токен истёк',
            status_code=401,
            error_code='TOKEN_EXPIRED',
        )


class TokenInvalid(AppError):
    def __init__(self) -> None:
        super().__init__(
            message='Невалидный токен',
            status_code=401,
            error_code='TOKEN_INVALID',
        )


class UserAlreadyExists(AppError):
    def __init__(self, email: str = '') -> None:
        # API-010/LIVE-013: Не раскрываем email для предотвращения enumeration
        super().__init__(
            message='Не удалось создать аккаунт с указанным email',
            status_code=409,
            error_code='USER_ALREADY_EXISTS',
        )


class UserNotFound(AppError):
    def __init__(self) -> None:
        super().__init__(
            message='Пользователь не найден',
            status_code=404,
            error_code='USER_NOT_FOUND',
        )


class InactiveUser(AppError):
    def __init__(self) -> None:
        super().__init__(
            message='Аккаунт деактивирован',
            status_code=403,
            error_code='INACTIVE_USER',
        )


# --- Resumes ---
class ResumeNotFound(AppError):
    def __init__(self) -> None:
        super().__init__(
            message='Резюме не найдено',
            status_code=404,
            error_code='RESUME_NOT_FOUND',
        )


class UnsupportedFileFormat(AppError):
    def __init__(self, detail: str = '') -> None:
        super().__init__(
            message=detail or 'Неподдерживаемый формат файла',
            status_code=400,
            error_code='UNSUPPORTED_FORMAT',
        )


class FileTooLarge(AppError):
    def __init__(self, max_mb: int = 10) -> None:
        super().__init__(
            message=f'Файл слишком большой (максимум {max_mb} МБ)',
            status_code=413,
            error_code='FILE_TOO_LARGE',
        )


class FileContentMismatch(AppError):
    def __init__(self) -> None:
        super().__init__(
            message='Содержимое файла не соответствует расширению',
            status_code=400,
            error_code='FILE_CONTENT_MISMATCH',
        )


# --- LLM ---
class LLMProviderUnavailable(AppError):
    def __init__(self, provider: str = 'gigachat') -> None:
        super().__init__(
            message='GigaChat временно недоступен',
            status_code=503,
            error_code='LLM_UNAVAILABLE',
            detail='Проверьте GIGACHAT_CREDENTIALS или повторите запрос позже.',
        )


class LLMAuthError(AppError):
    """Ключ GigaChat не задан или невалиден."""

    def __init__(self, provider: str = 'gigachat') -> None:
        super().__init__(
            message='Ключ авторизации GigaChat невалиден',
            status_code=400,
            error_code='LLM_AUTH_ERROR',
            detail='Укажите корректный GIGACHAT_CREDENTIALS в переменных окружения.',
        )


class LLMResponseError(AppError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            message='Невалидный ответ от LLM',
            status_code=502,
            error_code='LLM_RESPONSE_ERROR',
            detail=detail,
        )


# --- Домен HyreKit ---
class NotFound(AppError):
    def __init__(self, what: str = 'Объект') -> None:
        super().__init__(message=f'{what} не найден', status_code=404, error_code='NOT_FOUND')


class Forbidden(AppError):
    def __init__(self, message: str = 'Недостаточно прав') -> None:
        super().__init__(message=message, status_code=403, error_code='FORBIDDEN')


class Conflict(AppError):
    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message=message, status_code=409, error_code='CONFLICT', detail=detail)


class BadRequest(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=400, error_code='BAD_REQUEST')
