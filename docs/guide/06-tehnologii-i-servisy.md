# 6. Технологии и сервисы

Весь стек — открытое ПО под разрешительными лицензиями (ТЗ 3.5). Версии бэкенда закреплены в `requirements.txt` и `requirements-dev.txt`, фронтенда — в `frontend/package-lock.json`.

## Бэкенд (Python 3.11+)

| Библиотека | Версия | Лицензия | Зачем |
| -- | -- | -- | -- |
| FastAPI | 0.115.6 | MIT | HTTP API и генерация OpenAPI |
| Uvicorn | 0.34.0 | BSD-3 | ASGI-сервер |
| Pydantic / pydantic-settings | 2.10.5 / 2.7.1 | MIT | Схемы, валидация, конфигурация из окружения |
| SQLAlchemy (asyncio) | 2.0.37 | MIT | ORM |
| asyncpg | 0.30.0 | Apache-2.0 | Драйвер PostgreSQL |
| aiosqlite | 0.20.0 | MIT | SQLite для локального запуска и тестов |
| Alembic | 1.14.1 | MIT | Миграции |
| redis | 5.2.1 | MIT | Клиент Redis для лимитов |
| slowapi | 0.1.9 | MIT | Ограничение частоты запросов |
| PyJWT | 2.10.1 | MIT | Токены доступа |
| bcrypt | 4.2.1 | Apache-2.0 | Хеширование паролей |
| email-validator | 2.2.0 | Unlicense | Проверка адресов |
| python-multipart | 0.0.20 | Apache-2.0 | Загрузка файлов |
| PyMuPDF | 1.25.3 | AGPL-3.0 | Извлечение текста из PDF-резюме |
| python-docx | 1.1.2 | MIT | Извлечение текста из DOCX-резюме |
| reportlab | 5.0.1 | BSD | Генерация PDF-профиля |
| gigachat | 0.1.40 | MIT | Клиент GigaChat |
| httpx | 0.28.1 | BSD-3 | HTTP-клиент |
| tenacity | 9.0.0 | Apache-2.0 | Повторы внешних вызовов |
| structlog | 24.4.0 | MIT / Apache-2.0 | Логи |

Разработка: pytest 8.3.4, pytest-asyncio 0.24.0, pytest-cov 6.0.0, ruff 0.8.6, mypy 1.14.1, bandit 1.8.3, pip-audit 2.7.3.

## Фронтенд (Node.js 20+)

| Пакет | Версия | Лицензия | Зачем |
| -- | -- | -- | -- |
| React / React DOM | 19.2.4 | MIT | Интерфейс |
| React Router | 6.30.3 | MIT | Маршруты кабинетов |
| lucide-react | 0.576.0 | ISC | Иконки |
| TypeScript | 5.8.3 | Apache-2.0 | Типы |
| Vite | 6.4.1 | MIT | Сборка и dev-сервер |
| Vitest, Testing Library | 4.0.18, 16.3.2 | MIT | Тесты |
| ESLint | 9.39.3 | MIT | Линтер |

## Инфраструктура

| Компонент | Версия | Зачем |
| -- | -- | -- |
| PostgreSQL | 16 (alpine) | Основное хранилище |
| Redis | 7 (alpine) | Лимиты запросов |
| nginx | 1.27 (alpine) | Статика фронтенда и прокси `/api` |
| Mailpit | 1.21 | Перехват писем в локальном стенде |
| Docker Compose | v2 | Запуск всех компонентов одной командой |

## Шрифты и бренд

| Ресурс | Лицензия | Где |
| -- | -- | -- |
| JetBrains Mono — основной шрифт ФСП | SIL OFL 1.1 | `frontend/public/fonts/`, `src/app/assets/fonts/` (PDF-профиль) |
| TDAText — акцентный шрифт ФСП | SIL OFL 1.1 | `frontend/public/fonts/` |
| Логотип и паттерн ФСП | Брендбук ФСП, предоставлен организаторами | `frontend/public/brand/` |

## GigaChat

Используется в двух местах и нигде не принимает решений о грейде или подборке:

| Где | Что делает | Без ключа |
| -- | -- | -- |
| Разбор резюме (`candidates.resume_parser`) | Извлекает из текста ФИО, контакты, стек, роли, стаж, софт-скиллы в JSON; результат сливается с правилами | Регулярные выражения и словари технологий |
| Оценка коротких заданий (`challenges.service`) | Оценивает ответ по рубрике и пишет отзыв | Эвристика по полноте и ключевым словам задачи |

Задания теста модель не генерирует и не проверяет: это гарантирует сопоставимую сложность и воспроизводимую оценку (см. [раздел 3](03-metodika-ocenki.md)). Ключ задаётся `GIGACHAT_CREDENTIALS`; клиент — `src/app/llm/gigachat.py`.

Полный список сторонних компонентов и их лицензий — [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
