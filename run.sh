#!/usr/bin/env bash
# Платформа «Шесть» — запуск всего стека без systemd.
# Используется для разработки: поднимает портал, стенд карточек и два
# процесса «Игрушечек», пишет логи в logs/ и останавливает всё по Ctrl+C.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_BIN="${NODE_BIN:-/home/fun/local/node22/bin}"
mkdir -p "$ROOT/logs" "$ROOT/data"

if [[ -f "$ROOT/.env.stands" ]]; then
  set -a; source "$ROOT/.env.stands"; set +a
fi

pids=()
cleanup() {
  echo
  echo "останавливаю стенды…"
  for pid in "${pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "→ портал            http://0.0.0.0:8110"
"$ROOT/.venv/bin/uvicorn" studio.main:app --host 0.0.0.0 --port 8110 \
  >"$ROOT/logs/platform.log" 2>&1 &
pids+=($!)

echo "→ карточки          http://0.0.0.0:8200"
( cd "$ROOT/repos/TestovoeKartochki/backend" && \
  "$ROOT/.venv/bin/uvicorn" main:app --host 0.0.0.0 --port 8200 \
  >"$ROOT/logs/kartochki.log" 2>&1 ) &
pids+=($!)

if [[ -x "$NODE_BIN/node" ]]; then
  echo "→ игрушечки web     http://0.0.0.0:3100"
  ( cd "$ROOT/repos/Igrushki/.next/standalone" && \
    PATH="$NODE_BIN:$PATH" PORT=3100 HOSTNAME=0.0.0.0 NODE_ENV=production \
    node server.js >"$ROOT/logs/igrushki-web.log" 2>&1 ) &
  pids+=($!)

  echo "→ игрушечки api     http://0.0.0.0:3301"
  ( cd "$ROOT/repos/Igrushki/server" && \
    PATH="$NODE_BIN:$PATH" PORT=3301 HOST=0.0.0.0 NODE_ENV=development \
    JWT_SECRET="${JWT_SECRET:-dev-secret}" DB_PATH=./data/igruski.db \
    CORS_ORIGIN="http://192.168.51.81:3100,http://127.0.0.1:3100,http://localhost:3100" \
    node dist/server/src/index.js >"$ROOT/logs/igrushki-api.log" 2>&1 ) &
  pids+=($!)
else
  echo "! Node 22 не найден в $NODE_BIN — стенд «Игрушечек» пропущен"
fi

echo
echo "Готово. Портал: http://127.0.0.1:8110  (Ctrl+C — остановить)"
wait
