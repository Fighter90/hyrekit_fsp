# AGENTS.md

## Что это
HyreKit — платформа-агрегатор ИТ-вакансий с верифицированным профилем достижений участника ФСП (хакатон ФСП 2026, «Команда 1»). Кандидат подтверждает грейд тестом, работодатель получает подборку с объяснимым баллом и приглашает кандидатов. Продукт — [PRODUCT.md](PRODUCT.md), словарь — [CONTEXT.md](CONTEXT.md), визуальная система — [DESIGN.md](DESIGN.md).

## Источник истины
- Задачи — Linear, проект «HyreKit — платформа подбора ИТ-специалистов (ФСП)», ключи `FSP-N`.
- Спецификации — `docs/specs/fsp-N-*.md` по шаблону `docs/specs/_template.md`. Контракт API — `docs/spec/api.md`.
- Решения с альтернативами — `docs/decisions/` (ADR).
- Числа методики (пороги, веса, размер теста) — только из `src/app/assessment/engine.py` и `src/app/matching/service.py`; документация ссылается на них, а не дублирует своими словами.

## Команды
```bash
scripts/dev.sh                                   # API на :8000, SQLite .dev.db, демо-данные
cd frontend && npm run dev                       # SPA на :5173
ruff check src tests scripts && ruff format --check src tests scripts
pytest --cov=app                                 # бэкенд, порог покрытия 70 %
PYTHONPATH=src python scripts/validate.py        # валидация методики → docs/validation/results.md
PYTHONPATH=src python scripts/calibrate.py       # статус семейств заданий и исключение утёкших (FSP-33)
cd frontend && npm run lint && npm run build && npm test
docker compose up -d --build                     # весь стек: app, db, redis, mailpit, frontend
python scripts/smoke.py                          # дымовая проверка поднятого стенда
python scripts/load.py                           # нагрузка: p50/p95 ключевых операций
PYTHONPATH=src python scripts/export_openapi.py  # docs/openapi.json; CI проверяет актуальность
python scripts/build_docs.py                     # docs/HyreKit_Documentation.docx и .pdf из docs/guide/
```

## Правила
- SDD: спека до кода, тесты на каждый критерий приёмки.
- Одна задача Linear — одна ветка `feat/fsp-N-<slug>` — один PR в `main`; CI зелёный до слияния.
- Модули бэкенда: `models.py`, `service.py` (без HTTP), `router.py`. Методика — чистые функции без базы.
- Миграции — Alembic, `alembic/versions/`.
- Новое семейство заданий: генератор в `assessment/bank.py` на всех уровнях от `min_level`, отметка `conceptual`, тест в `tests/test_method/`, перезапуск `scripts/validate.py`.
- Секреты — только из окружения; `.env` в git не попадает.
- После изменения методики обновить `docs/guide/03-metodika-ocenki.md` цифрами из `docs/validation/results.md`.
- После правки `docs/guide/` пересобрать docx и pdf (`scripts/build_docs.py`); после правки схемы mermaid — сначала `node scripts/render_diagrams.cjs`.
- После изменения API — `scripts/export_openapi.py`, иначе CI упадёт.
