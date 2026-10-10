#!/usr/bin/env bash
# Выкатка HyreKit в Yandex Cloud без SSH: образы → Container Registry, ВМ с cloud-init, DNS в Timeweb.
#
#   YC_SA_KEY_JSON='{...}' TIMEWEB_TOKEN=... deploy/yc/deploy.sh          # первая выкатка или обновление
#   SKIP_DNS=1 deploy/yc/deploy.sh                                       # без изменения DNS
#   SKIP_BUILD=1 TAG=... deploy/yc/deploy.sh                             # образы с этим тегом уже в реестре
#   EXTRA_ENV_FILE=prod.env deploy/yc/deploy.sh                       # SMTP_*, GIGACHAT_*, YANDEX_GPT_* для приложения (в метаданные ВМ)
#   SSH_PUBKEY=~/.ssh/id_ed25519.pub deploy/yc/deploy.sh                 # доступ по SSH для отладки (необязательно)
#
# Повторный запуск идемпотентен: существующие ресурсы переиспользуются, ВМ получает новый тег и перезапускается.
set -euo pipefail

FOLDER_ID=${FOLDER_ID:-b1ged4dbgmd5sgonco2d}
ZONE=${ZONE:-ru-central1-a}
DOMAIN=${DOMAIN:-hyrekit.ru}
VM=${VM:-hyrekit}
REGISTRY_NAME=${REGISTRY_NAME:-hyrekit}
SA_NAME=${SA_NAME:-hyrekit-vm}
DISK_SIZE=${DISK_SIZE:-30}
DISK_TYPE=${DISK_TYPE:-network-ssd}  # network-hdd, если квота на SSD исчерпана
SSH_CIDR=${SSH_CIDR:-0.0.0.0/0}   # сузить до адресов команды
TAG=${TAG:-$(git rev-parse --short HEAD)}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

log() { printf '\n==> %s\n' "$*"; }
: "${YC_SA_KEY_JSON:?нужен авторизованный ключ сервисного аккаунта в YC_SA_KEY_JSON}"

# --- yc CLI и вход сервисным аккаунтом ---
if ! command -v yc >/dev/null; then
  log 'Ставлю yc CLI'
  curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash -s -- -i "$HOME/yandex-cloud" -n
  export PATH="$HOME/yandex-cloud/bin:$PATH"
fi
printf '%s' "$YC_SA_KEY_JSON" > "$WORK/deployer.json"
yc config profile create hyrekit-deploy >/dev/null 2>&1 || yc config profile activate hyrekit-deploy >/dev/null
yc config set service-account-key "$WORK/deployer.json"
yc config set folder-id "$FOLDER_ID"
yc config set compute-default-zone "$ZONE"

# --- Реестр и образы ---
log 'Container Registry'
REGISTRY_ID=$(yc container registry get --name "$REGISTRY_NAME" --format json 2>/dev/null | jq -r .id || true)
[ -n "$REGISTRY_ID" ] || REGISTRY_ID=$(yc container registry create --name "$REGISTRY_NAME" --format json | jq -r .id)
REGISTRY=cr.yandex/$REGISTRY_ID
yc iam create-token | docker login --username iam --password-stdin cr.yandex

if [ -z "${SKIP_BUILD:-}" ]; then
  log "Сборка и публикация образов с тегом $TAG"
  docker build -t "$REGISTRY/hyrekit-app:$TAG" "$ROOT"
  docker build --target production -t "$REGISTRY/hyrekit-frontend:$TAG" "$ROOT/frontend"
  docker push "$REGISTRY/hyrekit-app:$TAG"
  docker push "$REGISTRY/hyrekit-frontend:$TAG"
fi

# --- Сервисный аккаунт ВМ: только чтение реестра ---
log 'Сервисный аккаунт ВМ'
SA_ID=$(yc iam service-account get --name "$SA_NAME" --format json 2>/dev/null | jq -r .id || true)
[ -n "$SA_ID" ] || SA_ID=$(yc iam service-account create --name "$SA_NAME" --format json | jq -r .id)
yc container registry add-access-binding "$REGISTRY_ID" --role container-registry.images.puller \
  --service-account-id "$SA_ID" >/dev/null 2>&1 || true

# --- Статический IP и группа безопасности ---
log 'Статический IP'
IP=$(yc vpc address get --name "$VM-ip" --format json 2>/dev/null | jq -r '.external_ipv4_address.address' || true)
if [ -z "$IP" ] || [ "$IP" = null ]; then
  IP=$(yc vpc address create --name "$VM-ip" --external-ipv4 zone="$ZONE" --format json | jq -r '.external_ipv4_address.address')
fi
echo "IP: $IP"

NET_ID=$(yc vpc network list --format json | jq -r '.[0].id // empty')
[ -n "$NET_ID" ] || NET_ID=$(yc vpc network create --name default --format json | jq -r .id)
SUBNET_ID=$(yc vpc subnet list --format json | jq -r --arg z "$ZONE" '[.[] | select(.zone_id == $z)][0].id // empty')
[ -n "$SUBNET_ID" ] || SUBNET_ID=$(yc vpc subnet create --name "default-$ZONE" --network-id "$NET_ID" \
  --zone "$ZONE" --range 10.128.0.0/24 --format json | jq -r .id)
SG_ID=$(yc vpc security-group get --name "$VM-web" --format json 2>/dev/null | jq -r .id || true)
if [ -z "$SG_ID" ]; then
  SG_ID=$(yc vpc security-group create --name "$VM-web" --network-id "$NET_ID" \
    --rule 'direction=ingress,port=80,protocol=tcp,v4-cidrs=[0.0.0.0/0]' \
    --rule 'direction=ingress,port=443,protocol=tcp,v4-cidrs=[0.0.0.0/0]' \
    --rule "direction=ingress,port=22,protocol=tcp,v4-cidrs=[$SSH_CIDR]" \
    --rule 'direction=egress,from-port=0,to-port=65535,protocol=any,v4-cidrs=[0.0.0.0/0]' \
    --format json | jq -r .id)
fi

# --- ВМ ---
if yc compute instance get --name "$VM" >/dev/null 2>&1; then
  log "Обновляю ВМ до тега $TAG"
  yc compute instance add-metadata --name "$VM" --metadata "hyrekit-tag=$TAG,hyrekit-registry=$REGISTRY" >/dev/null
  [ -z "${EXTRA_ENV_FILE:-}" ] || yc compute instance add-metadata --name "$VM" \
    --metadata "hyrekit-extra-env=$(base64 -w0 < "$EXTRA_ENV_FILE")" >/dev/null
  yc compute instance restart --name "$VM" >/dev/null
else
  log 'Создаю ВМ'
  # Ключ ВМ для docker login: отдельный, с правом только читать образы
  yc iam key create --service-account-id "$SA_ID" --output "$WORK/vm-key.json" >/dev/null
  b64() { base64 -w0 < "$1"; }
  sed -e "s|__COMPOSE_B64__|$(b64 "$HERE/compose.prod.yaml")|" \
      -e "s|__CADDY_B64__|$(b64 "$HERE/Caddyfile")|" \
      -e "s|__SA_KEY_B64__|$(b64 "$WORK/vm-key.json")|" \
      -e "s|__UP_B64__|$(sed -e "s|__REGISTRY__|$REGISTRY|" -e "s|__TAG__|$TAG|" "$HERE/hyrekit-up.sh" | base64 -w0)|" \
      "$HERE/cloud-init.yaml" > "$WORK/user-data.yaml"
  yc compute instance create --name "$VM" --hostname "$VM" \
    --platform standard-v3 --cores 2 --memory 4 --core-fraction 100 \
    --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2404-lts,size=$DISK_SIZE,type=$DISK_TYPE \
    --network-interface "subnet-id=$SUBNET_ID,nat-ip-version=ipv4,nat-address=$IP,security-group-ids=$SG_ID" \
    --metadata "hyrekit-tag=$TAG,hyrekit-registry=$REGISTRY${EXTRA_ENV_FILE:+,hyrekit-extra-env=$(base64 -w0 < "$EXTRA_ENV_FILE")}" \
    --metadata-from-file "user-data=$WORK/user-data.yaml" \
    ${SSH_PUBKEY:+--ssh-key "$SSH_PUBKEY"} >/dev/null
fi

# --- Ежедневные снимки загрузочного диска, хранятся 7 последних ---
log 'Расписание снимков диска'
yc compute snapshot-schedule get --name "$VM-daily" >/dev/null 2>&1 ||
  yc compute snapshot-schedule create --name "$VM-daily" --expression '0 0 * * *' \
    --start-at "$(date -u +%Y-%m-%dT00:00:00Z)" --snapshot-count 7 >/dev/null
DISK_ID=$(yc compute instance get --name "$VM" --format json | jq -r .boot_disk.disk_id)
yc compute snapshot-schedule list-disks --name "$VM-daily" --format json | jq -e --arg d "$DISK_ID" 'any(.[]; .id == $d)' >/dev/null ||
  yc compute snapshot-schedule add-disks --name "$VM-daily" --disk-id "$DISK_ID" >/dev/null

# --- DNS в Timeweb ---
if [ -z "${SKIP_DNS:-}" ]; then
  : "${TIMEWEB_TOKEN:?нужен TIMEWEB_TOKEN или SKIP_DNS=1}"
  log "DNS: $DOMAIN и www → $IP"
  tw() { curl -sS --retry 3 -H "Authorization: Bearer $TIMEWEB_TOKEN" -H 'Content-Type: application/json' "$@"; }
  # A-запись корня правится на месте (второй корневой A Timeweb не принимает); записи www живут у www.$DOMAIN
  for fqdn in "$DOMAIN" "www.$DOMAIN"; do
    API=https://api.timeweb.cloud/api/v1/domains/$fqdn/dns-records
    id=$(tw "$API" | jq -r '[.dns_records[]? | select(.type == "A")][0].id // empty')
    if [ -n "$id" ]; then
      tw -X PATCH "$API/$id" -d "{\"type\":\"A\",\"value\":\"$IP\"}" >/dev/null
    elif [ "$fqdn" = "$DOMAIN" ]; then
      tw -X POST "$API" -d "{\"type\":\"A\",\"value\":\"$IP\"}" >/dev/null
    else
      tw -X POST "https://api.timeweb.cloud/api/v1/domains/$DOMAIN/dns-records" \
        -d "{\"type\":\"A\",\"value\":\"$IP\",\"subdomain\":\"www\"}" >/dev/null
    fi
  done
fi

# --- Ожидание и дымовая проверка ---
log "Жду https://$DOMAIN/health (первая загрузка ВМ и выпуск сертификата — несколько минут)"
for _ in $(seq 1 90); do
  if curl -sf -m 5 "https://$DOMAIN/health" >/dev/null || curl -sf -m 5 -H "Host: $DOMAIN" "http://$IP/health" >/dev/null; then
    break
  fi
  sleep 10
done
python "$ROOT/scripts/smoke.py" --base "https://$DOMAIN" --no-mail
