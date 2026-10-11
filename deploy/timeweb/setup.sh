#!/bin/bash
# Установка и обновление резервной площадки на TimeWeb (Ubuntu). Запуск: bash deploy/timeweb/setup.sh
# Ключи GigaChat, YandexGPT и SMTP — строками KEY=value в deploy/timeweb/extra.env (необязательно).
set -euo pipefail
cd "$(dirname "$0")"
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q /swapfile /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose-v2 >/dev/null 2>&1 || \
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose-plugin >/dev/null
  systemctl enable --now docker
fi
if [ ! -f secrets.env ]; then
  printf 'POSTGRES_PASSWORD=%s\nSECRET_KEY=%s\n' "$(openssl rand -hex 16)" "$(openssl rand -hex 32)" > secrets.env
  chmod 600 secrets.env
fi
. ./secrets.env
PUBLIC_URL=${PUBLIC_URL:-https://83-217-223-211.sslip.io}
cat > .env <<ENV
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
SECRET_KEY=$SECRET_KEY
ENVIRONMENT=production
DEBUG=false
PUBLIC_URL=$PUBLIC_URL
CORS_ORIGINS=["https://83-217-223-211.sslip.io","https://hyrekit.ru","https://www.hyrekit.ru","http://83.217.223.211"]
SEED_DEMO=true
DOCS_ENABLED=true
MAIL_FROM=HyreKit <noreply@hyrekit.ru>
ENV
if [ -f extra.env ]; then cat extra.env >> .env; fi
chmod 600 .env
docker compose build
docker compose up -d --remove-orphans
docker compose ps
