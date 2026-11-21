#!/usr/bin/env bash
# Деплой сертификата: копирует свежие файлы в tls/live и перезапускает HTTPS-сервис.
# Вызывается certbot как --deploy-hook, поэтому переменные RENEWED_LINEAGE задаёт он же.
set -euo pipefail

LINEAGE="${RENEWED_LINEAGE:-/home/fun/.local/certbot/live/devyatkinprod.ru}"
DEST="/home/fun/projects/portfolio-platform/tls/live"

install -m 644 "$LINEAGE/fullchain.pem" "$DEST/fullchain.pem"
install -m 600 "$LINEAGE/privkey.pem" "$DEST/privkey.pem"

systemctl --user restart portfolio-tls.service
echo "[deploy-cert] сертификат обновлён и сервис перезапущен: $(date -Iseconds)"
