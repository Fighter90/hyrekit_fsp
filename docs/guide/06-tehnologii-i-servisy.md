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
| httpx | 0.28.1 | BSD-3 | HTTP-клиент: YandexGPT, OIDC ФСП ID |
| tenacity | 9.0.0 | Apache-2.0 | Повторы внешних вызовов |
| structlog | 24.4.0 | MIT / Apache-2.0 | Логи |

Разработка: pytest 8.3.4, pytest-asyncio 0.24.0, pytest-cov 6.0.0, ruff 0.8.6, mypy 1.14.1, bandit 1.8.3, pip-audit 2.7.3.

## Фронтенд (Node.js 20+)

| Пакет | Версия | Лицензия | Зачем |
| -- | -- | -- | -- |
| React / React DOM | 19.2.4 | MIT | Интерфейс |
| React Router | 6.30.3 | MIT | Маршруты кабинетов |
| lucide-react | 0.576.0 | ISC | Иконки |
| CodeMirror | 6.0.2 (`@codemirror/view` 6.43.14, `@codemirror/state` 6.7.6) | MIT | Редактор кода в Code Arena |
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
| Caddy | 2.8 (alpine) | HTTPS с сертификатом Let's Encrypt на площадке (`deploy/yc/compose.prod.yaml`) |
| Node.js | 20 (бинарник в образе `app`) | Запуск решений Code Arena на JavaScript |

## Шрифты и бренд

| Ресурс | Лицензия | Где |
| -- | -- | -- |
| JetBrains Mono — основной шрифт ФСП | SIL OFL 1.1 | `frontend/public/fonts/`, `src/app/assets/fonts/` (PDF-профиль) |
| TDAText — акцентный шрифт ФСП | SIL OFL 1.1 | `frontend/public/fonts/` |
| Логотип и паттерн ФСП | Брендбук ФСП, предоставлен организаторами | `frontend/public/brand/` |

## Модели LLM: GigaChat и YandexGPT

Модель подключена через цепочку провайдеров `src/app/llm/chain.py`. Запрос уходит первому настроенному провайдеру из `LLM_PROVIDERS` (по умолчанию GigaChat, затем YandexGPT). Если он не ответил или вернул ответ без JSON, запрос повторяется у следующего. Если не ответил никто, работают правила. Кто написал результат, записано в поле `source` (`gigachat`, `yandexgpt` или `rules`) и показано в интерфейсе.

| Провайдер | Клиент | Доступ | Переменные |
| -- | -- | -- | -- |
| GigaChat (Сбер) | `src/app/llm/gigachat.py`, SDK `gigachat` | Authorization Key из личного кабинета developers.sber.ru, OAuth-токен обновляется автоматически | `GIGACHAT_CREDENTIALS`, `GIGACHAT_SCOPE`, `GIGACHAT_MODEL` |
| YandexGPT (Yandex AI Studio) | `src/app/llm/yandexgpt.py`, REST через `httpx` | API-ключ сервисного аккаунта с ролью `ai.languageModels.user` и ID каталога | `YANDEX_GPT_API_KEY`, `YANDEX_GPT_FOLDER_ID`, `YANDEX_GPT_MODEL` |

Где используется модель. Нигде она не принимает решений о грейде или подборке:

| Где | Что делает | Без модели |
| -- | -- | -- |
| Разбор резюме (`candidates.resume_parser`) | Извлекает из текста ФИО, контакты, стек, роли, стаж, софт-скиллы в JSON; результат сливается с правилами | Регулярные выражения и словари технологий |
| Оценка коротких заданий (`challenges.service`) | Оценивает ответ по рубрике и пишет отзыв | Эвристика по полноте и ключевым словам задачи |
| Разбор решения Code Arena (`arena.feedback`) | Пишет, где и почему упало решение, и даёт до пяти замечаний по коду | Шаблоны по вердикту, типичные ошибки задачи и статический разбор кода |

Состояние провайдеров показывает `GET /api/v1/llm/status` (нужен вход): настроен ли ключ, ответил ли проверочный запрос, ошибка, задержка и последняя ошибка в рабочих запросах (`last_error`). Результат кэшируется на 5 минут. Задания теста модель не генерирует и не проверяет: это гарантирует сопоставимую сложность и воспроизводимую оценку (см. [раздел 3](03-metodika-ocenki.md)). Решение и альтернативы — [ADR 0002](../decisions/0002-gigachat.md), спека — [llm-provajdery.md](../specs/llm-provajdery.md).

Полный список сторонних компонентов и их лицензий — [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
