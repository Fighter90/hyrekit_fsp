---
description: Взять задачу Linear FSP-N и провести её по SDD до PR
agent: build
---
Задача: $ARGUMENTS

Пройди путь задачи HyreKit (подробно — `docs/process.md`):

1. Прочитай задачу в Linear через MCP `linear`, затем `docs/progress.md` и связанные спеки в `docs/specs/`.
2. Ветка `feat/fsp-N-<slug>` от свежего `main`.
3. Спека до кода: вызови агента @spec, если спеки ещё нет.
4. Код по правилам `AGENTS.md` и тест на каждый критерий приёмки.
5. Прогони /check и почини всё красное.
6. Обнови то, что затронуто: `docs/spec/api.md` и `docs/openapi.json`, `docs/guide/` с пересборкой docx и pdf, README, CHANGELOG, `CONTEXT.md`, `docs/progress.md`.
7. Вызови агента @review и исправь найденное.
8. Покажи итог и спроси, пушить ли ветку и открывать ли PR в `main`. Задачу в Linear переводи в Done только после слияния.
