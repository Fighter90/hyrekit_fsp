---
description: Поднять стенд локально и прогнать сквозной браузерный тест
---
Прогони сквозную проверку HyreKit. Адрес стенда: $ARGUMENTS (пусто — локальный стенд).

1. Локально: `scripts/dev.sh` (API на :8000) и `cd frontend && npm run dev` (SPA на :5173) в фоне; дождись `curl -s localhost:8000/health`.
2. `python scripts/smoke.py` — дымовая проверка API.
3. `NODE_PATH=<node_modules с playwright> node scripts/e2e.cjs` — браузерный сценарий; для стенда добавь `--base https://hyrekit.ru`.

Покажи итоги OK/FAIL и скриншоты упавших шагов. Останови фоновые процессы, которые запустил.
