# Runbook

## Выкатка в Yandex Cloud

Скрипт `deploy/yc/deploy.sh` собирает образы, кладёт их в Container Registry и создаёт ВМ, которая сама поднимает стек через cloud-init. SSH не нужен.

Что нужно заранее:

- сервисный аккаунт с ролями `editor` и `container-registry.admin` в каталоге площадки и его авторизованный ключ (`yc iam key create --service-account-name hyrekit-deploy --output key.json`);
- токен API Timeweb для зоны `hyrekit.ru`;
- Docker, `jq`, `curl` и Python с `httpx` на машине, откуда идёт выкатка.

```bash
export YC_SA_KEY_JSON="$(cat key.json)" TIMEWEB_TOKEN=...
deploy/yc/deploy.sh                # FOLDER_ID, ZONE, DOMAIN, TAG, SSH_CIDR, SSH_PUBKEY — переопределяются окружением
```

Скрипт идемпотентен. В конце он ждёт `https://hyrekit.ru/health` и запускает `scripts/smoke.py --no-mail`.

Секреты базы и `SECRET_KEY` генерируются на ВМ при первой загрузке (`/opt/hyrekit/secrets.env`) и не покидают её. Дополнительные переменные (`GIGACHAT_CREDENTIALS`, `SMTP_*`) передаются метаданными ВМ:

```bash
yc compute instance add-metadata --name hyrekit \
  --metadata hyrekit-extra-env="$(printf 'GIGACHAT_CREDENTIALS=...\nSMTP_HOST=...\n' | base64 -w0)"
yc compute instance restart --name hyrekit
```

## Обновление

Повторный запуск `deploy/yc/deploy.sh`: новые образы с тегом текущего коммита, тег в метаданных ВМ, перезапуск. Миграции применяются при старте контейнера `app` (`alembic upgrade head`).

Ручной вариант на сервере без реестра:

```bash
git clone https://github.com/Fighter90/hyrekit_fsp.git && cd hyrekit_fsp && cp .env.example .env
docker compose -f docker-compose.yml -f deploy/yc/docker-compose.yaml up -d --build
```

## Резервная копия и восстановление базы

На ВМ стек лежит в `/opt/hyrekit`, команды — `docker compose -f compose.prod.yaml --env-file .env ...`.

```bash
docker compose exec db pg_dump -U hyrekit hyrekit | gzip > backup-$(date +%F).sql.gz
gunzip -c backup-YYYY-MM-DD.sql.gz | docker compose exec -T db psql -U hyrekit hyrekit
```

## Частые проблемы

| Симптом | Причина и решение |
| -- | -- |
| `app` в статусе unhealthy, в логах `name resolution` | База ещё не готова; `docker compose restart app` |
| Запуск падает с ошибкой про SECRET_KEY | В production слабый ключ запрещён; задать случайный 64-символьный |
| Письма не приходят | Пустой `SMTP_HOST` — ссылка подтверждения в `docker compose logs app`; локально письма в Mailpit на :8025 |
| Разбор резюме без GigaChat хуже | Задать `GIGACHAT_CREDENTIALS`; без ключа работают правила |
| Нужно пересоздать демо-данные | `docker compose down -v && docker compose up -d` — база создаётся заново |
