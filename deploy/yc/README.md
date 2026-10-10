# Площадка в Yandex Cloud

Целевой адрес — <https://hyrekit.ru>. Схема для хакатонной нагрузки (десятки одновременных пользователей):

| Ресурс | Параметры |
| -- | -- |
| Compute Cloud, ВМ | Ubuntu 24.04, 2 vCPU, 4 ГБ RAM, 30 ГБ SSD, публичный статический IP |
| Сеть | Группа безопасности: входящие 22 (только адреса команды), 80, 443 |
| DNS | A-записи `hyrekit.ru` и `www.hyrekit.ru` на статический IP |
| TLS | Caddy с автоматическим сертификатом Let's Encrypt |
| Резервные копии | Расписание снимков диска раз в сутки, хранение 7 дней |

Файлы:

- `deploy.sh` — выкатка одной командой без SSH: образы в Container Registry, статический IP, группа безопасности, ВМ с cloud-init, A-записи в Timeweb, дымовая проверка.
- `compose.prod.yaml` — стек на ВМ из готовых образов реестра (app, db, redis, frontend, Caddy).
- `cloud-init.yaml` — первичная настройка ВМ; кладёт на неё `hyrekit-up.sh` в base64 (`yc` подставляет переменные окружения в файлы метаданных, поэтому скрипт с `$` напрямую передавать нельзя).
- `hyrekit-up.sh` — на каждой загрузке берёт тег версии из метаданных ВМ (запасной — вшитый при создании) и поднимает стек.
- `docker-compose.yaml` — дополнение к корневому `docker-compose.yml` для ручной сборки прямо на сервере.
- `Caddyfile` — HTTPS и проксирование.

Переменные `deploy.sh`: `FOLDER_ID`, `ZONE`, `TAG`, `SKIP_DNS=1`, `SKIP_BUILD=1` (образы с тегом `TAG` уже в реестре), `DISK_TYPE` и `DISK_SIZE` (в новом облаке квота на SSD бывает нулевой — `DISK_TYPE=network-hdd DISK_SIZE=15`).

Реестр Yandex Cloud не принимает OCI-индекс с аттестациями, который пушит Docker с containerd-хранилищем. Если `docker push` падает с `Cannot read manifest data`, собирать так: `docker buildx build --provenance=false --sbom=false --output type=image,name=<образ>,push=true,oci-mediatypes=false`, затем `SKIP_BUILD=1`.

Пошаговая выкатка и обслуживание — [docs/runbook.md](../../docs/runbook.md).
