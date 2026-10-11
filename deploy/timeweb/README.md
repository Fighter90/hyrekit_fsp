# Резервная площадка на TimeWeb

Резервный стенд на случай сбоя Yandex Cloud: ВМ TimeWeb (Ubuntu, 1 vCPU, 1 ГБ), адрес <https://83-217-223-211.sslip.io>. Образы собираются прямо на ВМ, реестр Яндекса не нужен.

```bash
# на рабочей машине: собрать фронтенд (на ВМ с 1 ГБ сборка Vite не помещается)
cd frontend && APP_COMMIT=$(git rev-parse --short HEAD) npm run build && cp -r dist dist-prebuilt && cd ..
# скопировать репозиторий на ВМ в /opt/hyrekit (без node_modules), затем на ВМ:
bash deploy/timeweb/setup.sh
```

`setup.sh` включает подкачку на 2 ГБ, ставит Docker, создаёт `secrets.env` (пароль базы, `SECRET_KEY`) и `.env`, собирает и поднимает стек: app, PostgreSQL, Redis, nginx с фронтендом, Caddy с HTTPS. Ключи GigaChat и YandexGPT — строками `KEY=value` в `deploy/timeweb/extra.env` (в git не попадает). Повторный запуск обновляет площадку.

Ограничения: на TimeWeb закрыты исходящие порты 25, 465, 587 и 2525, поэтому письма подтверждения с этой площадки не уходят. `hyrekit.ru` в `Caddyfile` получит сертификат, когда A-запись домена будет указывать на 83.217.223.211.
