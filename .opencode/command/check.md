---
description: Линтер и тесты бэкенда и фронтенда, как в CI
---
Запусти проверки HyreKit и покажи вывод каждой:

!`ruff check src tests scripts && ruff format --check src tests scripts`
!`pytest -q --cov=app 2>&1 | tail -5`
!`PYTHONPATH=src python scripts/export_openapi.py --check`
!`cd frontend && npm run lint && npm run build 2>&1 | tail -3 && npm test 2>&1 | tail -6`

Если что-то красное — найди причину и предложи исправление. Ничего не пропускай и не отключай тесты.
