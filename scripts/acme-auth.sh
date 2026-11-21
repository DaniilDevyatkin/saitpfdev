#!/usr/bin/env bash
# Ручная DNS-проверка для certbot: выкладывает значение TXT в файл и ждёт
# подтверждения, что запись добавлена в панели reg.ru (маркер-файл).
set -euo pipefail

OUT="/home/fun/projects/portfolio-platform/tls/acme-challenge.txt"
GO="/home/fun/projects/portfolio-platform/tls/acme-go"

printf 'имя: _acme-challenge.%s\nзначение: %s\n' "$CERTBOT_DOMAIN" "$CERTBOT_VALIDATION" > "$OUT"
echo "[acme-auth] ждём подтверждения: touch $GO"

for _ in $(seq 1 360); do          # ждём до 30 минут
    [ -f "$GO" ] && break
    sleep 5
done

if [ ! -f "$GO" ]; then
    echo "[acme-auth] время ожидания истекло" >&2
    exit 1
fi
rm -f "$GO"
echo "[acme-auth] подтверждение получено, отдаём проверку Let's Encrypt"
