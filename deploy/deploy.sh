#!/usr/bin/env bash
# One-shot deploy helper for Stamp AI Service
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] Prepare dirs..."
mkdir -p data/uploads data/outputs data/logs data/temp data/models/u2net deploy/certs

if [[ ! -f .env ]]; then
  echo "[2/5] Create .env from .env.example"
  cp .env.example .env
else
  echo "[2/5] .env exists, skip"
fi

echo "[3/5] Build images..."
# Prefer .env build args if present
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env || true
  set +a
fi
export APT_MIRROR="${APT_MIRROR:-mirrors.aliyun.com}"
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
echo "  APT_MIRROR=${APT_MIRROR}"
echo "  PIP_INDEX_URL=${PIP_INDEX_URL}"
docker compose build

echo "[4/5] Start services..."
docker compose up -d

echo "[5/5] Wait health..."
for i in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${HOST_PORT:-8000}/api/health" >/dev/null 2>&1 \
    || curl -fsS "http://127.0.0.1:${NGINX_HTTP_PORT:-80}/api/health" >/dev/null 2>&1; then
    echo "Service is healthy."
    docker compose ps
    echo
    echo "Docs:    http://<server-ip>/docs"
    echo "Health:  http://<server-ip>/api/health"
    echo "Direct:  http://<server-ip>:${HOST_PORT:-8000}/docs  (if HOST_PORT published)"
    exit 0
  fi
  sleep 3
done

echo "Health check timeout. Recent logs:"
docker compose logs --tail=80
exit 1
