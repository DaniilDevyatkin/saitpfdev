#!/usr/bin/env bash
# Убирает временные файлы ручной DNS-проверки после выпуска сертификата.
set -euo pipefail
rm -f /home/fun/projects/portfolio-platform/tls/acme-challenge.txt \
      /home/fun/projects/portfolio-platform/tls/acme-go
echo "[acme-cleanup] временные файлы проверки удалены"
