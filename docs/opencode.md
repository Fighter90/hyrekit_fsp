# Разработка в OpenCode

В репозитории лежит готовая настройка [OpenCode](https://opencode.ai): правила проекта, подключения к Linear и GitHub, агенты и команды по процессу Spec-Driven Development. Достаточно склонировать репозиторий, авторизоваться и запустить `opencode` в его корне.

## Что где лежит

| Файл | Что делает |
| -- | -- |
| [`AGENTS.md`](../AGENTS.md) | Правила проекта: команды, модули, SDD. OpenCode читает его сам в каждой сессии |
| [`opencode.json`](../opencode.json) | Дополнительные инструкции (`CONTEXT.md`, `docs/process.md`), MCP-серверы, разрешения |
| [`.opencode/agent/spec.md`](../.opencode/agent/spec.md) | Агент `@spec`: пишет спецификацию `docs/specs/fsp-N-*.md` по задаче Linear до кода |
| [`.opencode/agent/review.md`](../.opencode/agent/review.md) | Агент `@review`: проверяет изменения по правилам `AGENTS.md`, только читает |
| [`.opencode/command/task.md`](../.opencode/command/task.md) | `/task FSP-N`: задача от Linear до готовой ветки |
| [`.opencode/command/check.md`](../.opencode/command/check.md) | `/check`: линтер, тесты и проверка `openapi.json`, как в CI |
| [`.opencode/command/docs.md`](../.opencode/command/docs.md) | `/docs`: пересборка `openapi.json`, результатов валидации, docx и pdf |
| [`.opencode/command/e2e.md`](../.opencode/command/e2e.md) | `/e2e [адрес]`: smoke и браузерный сквозной тест на локальном стенде или на hyrekit.ru |

Спецификации — [`docs/specs/`](specs/README.md), контракт API — [`docs/spec/api.md`](spec/api.md), решения — [`docs/decisions/`](decisions/), ход работ — [`docs/progress.md`](progress.md).

## Подключение

1. Установите OpenCode: `npm i -g opencode-ai` (или `curl -fsSL https://opencode.ai/install | bash`). Настройка проверена на версии 1.18.
2. Подготовьте окружение разработчика по README («Быстрый старт для разработчика»): Python 3.11+, Node.js 20+, `pip install -r requirements-dev.txt`, `cd frontend && npm ci`.
3. Войдите в провайдера модели: `opencode auth login` (Anthropic, OpenAI или другой). Модель выбирается в самом OpenCode командой `/models`; в `opencode.json` она не задана, чтобы у каждого была своя.
4. Linear: `opencode mcp auth linear` — откроется вход через браузер в рабочее пространство `fsphackathon`.
5. GitHub: задайте токен с доступом к `Fighter90/hyrekit_fsp` (права на contents и pull requests) в переменной окружения перед запуском:
   ```bash
   export GITHUB_TOKEN=ghp_...
   ```
   Без токена MCP `github` не подключится, но `git` и остальная работа доступны.
6. Браузерные проверки через MCP Playwright выключены по умолчанию: включите `mcp.playwright.enabled` в `opencode.json` локально, если нужно, чтобы модель сама ходила по интерфейсу.
7. Запустите `opencode` в корне репозитория. `opencode mcp list` покажет, какие серверы подключены.

Ключи GigaChat, YandexGPT, SMTP и облака в репозиторий не попадают: для локальной работы они берутся из `.env` (образец — `.env.example`), без них разборы пишут правила, а письма уходят в лог.

## Как вести задачу

```
/task FSP-62
```

Команда читает задачу в Linear, создаёт ветку `feat/fsp-62-<slug>`, просит `@spec` написать спецификацию, ведёт код и тесты, гоняет `/check`, обновляет документацию, зовёт `@review` и перед `git push` спрашивает подтверждение. Дальше — PR в `main`, зелёный CI и слияние; задача в Linear закрывается после слияния.

Разрешения в `opencode.json`: правка файлов и команды разрешены, а `git push`, `git reset --hard`, `rm -rf`, `docker compose down -v`, `alembic downgrade` и выкатка `deploy/yc/deploy.sh` всегда спрашивают подтверждение.
