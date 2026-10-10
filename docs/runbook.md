# Runbook

## Первая выкатка в Yandex Cloud

1. Создать ВМ по параметрам из [deploy/yc/README.md](../deploy/yc/README.md), привязать статический IP, открыть 80 и 443.
2. Направить A-записи `hyrekit.ru` и `www.hyrekit.ru` на IP.
3. На ВМ:

   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
   git clone https://github.com/Fighter90/hyrekit_fsp.git && cd hyrekit_fsp
   cp .env.example .env
   # в .env: ENVIRONMENT=production, SECRET_KEY=$(openssl rand -hex 32),
   # POSTGRES_PASSWORD, GIGACHAT_CREDENTIALS, SMTP_* для реальной почты
   docker compose -f docker-compose.yml -f deploy/yc/docker-compose.yaml up -d --build
   ```

4. Проверить: `curl -s https://hyrekit.ru/health`, вход демо-аккаунтами, письмо подтверждения.

## Обновление

```bash
cd hyrekit_fsp && git pull
docker compose -f docker-compose.yml -f deploy/yc/docker-compose.yaml up -d --build
```

Миграции применяются при старте контейнера `app` (`alembic upgrade head`).

## Резервная копия и восстановление базы

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
