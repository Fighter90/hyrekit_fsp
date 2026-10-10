# 5. Запуск и демо

## Вариант 1. Docker Compose — одна команда

Нужно: Docker 24+ с Compose v2, 2 ГБ свободной памяти. Работает на Linux, macOS и Windows (WSL2).

```bash
git clone https://github.com/Fighter90/hyrekit_fsp.git
cd hyrekit_fsp
cp .env.example .env
docker compose up -d --build
```

| Что | Адрес |
| -- | -- |
| Приложение | <http://localhost:3000> |
| Swagger UI | <http://localhost:8000/docs> |
| Письма подтверждения (Mailpit) | <http://localhost:8025> |

При первом старте API применяет миграцию и создаёт демо-данные: два аккаунта, компанию с тремя вакансиями и двумя заданиями, 120 синтетических кандидатов по шести направлениям. Повторный старт ничего не дублирует.

Проверка, что всё поднялось:

```bash
curl -s http://localhost:8000/health        # {"status":"ok",...}
docker compose ps                           # app, db, redis, mailpit, frontend — healthy / running
```

Полная проверка стенда одной командой — `python scripts/smoke.py` (нужен `httpx` из `requirements.txt`): 28 шагов сквозного сценария через живой API, включая письмо в Mailpit; для удалённого стенда — `--base https://hyrekit.ru --no-mail`.

Остановка: `docker compose down`; с удалением данных — `docker compose down -v`.

## Вариант 2. Локально без Docker и PostgreSQL

Нужно: Python 3.11+, Node.js 20+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
PATH=$PWD/.venv/bin:$PATH scripts/dev.sh          # API на http://localhost:8000, база — файл .dev.db (SQLite)

# во втором терминале
cd frontend && npm ci && npm run dev               # http://localhost:5173, /api проксируется на :8000
```

`scripts/dev.sh` выставляет `DATABASE_URL` на SQLite, применяет миграцию и запускает API с автоперезагрузкой. Демо-данные создаются так же, как в Docker. Ссылка подтверждения почты без SMTP печатается в лог API.

## Демо-аккаунты

| Роль | Почта | Пароль | Что внутри |
| -- | -- | -- | -- |
| Кандидат | `candidate@hyrekit.ru` | `HyreKit2026` | Пустой профиль — путь проходится с нуля |
| Работодатель | `employer@hyrekit.ru` | `HyreKit2026` | Компания «ТехноПлатформа», 3 вакансии с подборками, 2 коротких задания |

Синтетические кандидаты (`talent01@demo.hyrekit.ru` … `talent120@demo.hyrekit.ru`, тот же пароль) прошли тест через симуляцию по той же модели, что и валидация, поэтому их категории и рейтинги согласованы с методикой. Около 65 % привязали ФСП ID; часть ID без истории — так видно, как система показывает кандидата без достижений.

## Демо за 5 минут

Сквозной сценарий ТЗ 3.3.

**Кандидат** (`candidate@hyrekit.ru`):

1. «Профиль» → загрузить PDF-резюме: поля заполнятся автоматически, распознанные подсвечены. Либо заполнить вручную.
2. «Тестирование» → опрос: отрасль, Backend, стаж, стек, предполагаемый грейд Middle.
3. Пройти тест: 10 заданий, таймер, карта вопросов, ответы сохраняются сами.
4. Результат: балл, разбор по темам, присвоенная категория «Backend · Middle» или предложение пересдать уровнем ниже.
5. «Настройки» → дать согласие на публикацию, привязать ФСП ID, например `FSP-123457` (есть история) или `FSP-123450` (истории нет).

**Работодатель** (`employer@hyrekit.ru`, в другом браузере или окне инкогнито):

6. «Потребности» → «Python backend-разработчик» → подборка: кандидаты по убыванию соответствия, полосы компонентов балла, причины, недостающий стек. Свежий кандидат из шагов 1–5 появится здесь.
7. Отфильтровать «Только с достижениями ФСП» и сбросить фильтр — исходная подборка не теряется.
8. Вкладка «Тест под вакансию» — темы из стека вакансии и два разных варианта одинаковой сложности.
9. Открыть кандидата → контакты скрыты → «Пригласить»: описание, вилка 250 000 – 320 000 ₽, способ связи.

**Кандидат**:

10. «Приглашения» → видно компанию и зарплату → «Принять».

**Работодатель**:

11. «Приглашения и отклики» → статус «принято», у кандидата открылись ФИО и контакты.

Дополнительно: кандидат откликается на опубликованную вакансию в «Вакансиях», работодатель видит отклик и раскрытые контакты; кандидат отвечает на короткое задание в «Челленджах», работодатель видит ответ с оценкой.

## Переменные окружения

| Переменная | По умолчанию | Назначение |
| -- | -- | -- |
| `SECRET_KEY` | — (обязательна) | Подпись JWT; в production слабый ключ останавливает запуск |
| `DATABASE_URL` | PostgreSQL на localhost | `postgresql+asyncpg://…` или `sqlite+aiosqlite:///…` |
| `REDIS_URL` | `redis://localhost:6379/0` | Лимиты запросов |
| `ENVIRONMENT` | `development` | `production` включает строгие проверки |
| `CORS_ORIGINS` | localhost | Разрешённые адреса фронтенда |
| `GIGACHAT_CREDENTIALS` | пусто | Ключ GigaChat; без него разбор резюме и оценка заданий идут по правилам |
| `GIGACHAT_SCOPE`, `GIGACHAT_MODEL` | `GIGACHAT_API_PERS`, `GigaChat` | Параметры GigaChat |
| `SEED_DEMO` | `true` | Демо-аккаунты и синтетический банк при старте |
| `PUBLIC_URL` | `http://localhost:3000` | Адрес фронтенда в ссылках писем |
| `DOCS_ENABLED` | `true` | Swagger UI и `/openapi.json` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`, `MAIL_FROM` | пусто | Почта; пустой `SMTP_HOST` — ссылка в лог |

## Сборка и проверки

```bash
ruff check src tests scripts && ruff format --check src tests scripts   # линтер и формат
pytest --cov=app                                                         # тесты бэкенда с покрытием
PYTHONPATH=src python scripts/validate.py                                # валидация методики → docs/validation/results.md
cd frontend && npm run lint && npm run build && npm test                 # фронтенд
```

## Развёртывание в Yandex Cloud

Целевая площадка — <https://hyrekit.ru>. Схема: одна ВМ Compute Cloud (2 vCPU, 4 ГБ) с Docker Compose из этого репозитория, Caddy или nginx с сертификатом Let's Encrypt перед контейнером `frontend`, ежедневный снимок диска. Пошаговая инструкция — [docs/runbook.md](../runbook.md), файлы площадки — `deploy/yc/`.
