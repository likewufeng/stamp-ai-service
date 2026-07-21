#!/usr/bin/env bash
# One-shot deploy helper for Stamp AI Service (app only, no nginx)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/6] Prepare dirs..."
mkdir -p data/uploads data/outputs data/logs data/temp data/models/u2net

if [[ ! -f .env ]]; then
  echo "[2/6] Create .env from .env.example"
  cp .env.example .env
else
  echo "[2/6] .env exists, skip"
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env || true
  set +a
fi

export APT_MIRROR="${APT_MIRROR:-mirrors.aliyun.com}"
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export HOST_PORT="${HOST_PORT:-18080}"

# 避免沿用旧 .env 里的 80/8000（极易被占用）
if [[ "${HOST_PORT}" == "80" || "${HOST_PORT}" == "8000" ]]; then
  echo "WARN: HOST_PORT=${HOST_PORT} is commonly occupied; override to 18080"
  echo "      Please edit .env: HOST_PORT=18080"
  export HOST_PORT=18080
fi

echo "[3/6] Verify build files..."
if ! grep -q "APT_MIRROR" Dockerfile; then
  echo "ERROR: Dockerfile is outdated (no APT_MIRROR). Please sync latest Dockerfile."
  exit 1
fi
if [[ ! -f .dockerignore ]]; then
  echo "ERROR: missing .dockerignore (build context will be huge)."
  exit 1
fi
echo "  Dockerfile OK"
echo "  .dockerignore OK"
echo "  APT_MIRROR=${APT_MIRROR}"
echo "  PIP_INDEX_URL=${PIP_INDEX_URL}"
echo "  HOST_PORT=${HOST_PORT}"

echo "[4/6] Build images..."
docker compose build --build-arg "APT_MIRROR=${APT_MIRROR}" --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL}"

echo "[5/6] Start service..."
docker compose up -d

echo "[6/6] Wait health..."
for i in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${HOST_PORT}/api/health" >/dev/null 2>&1; then
    echo "Service is healthy."
    docker compose ps
    echo
    echo "=========================================="
    echo "  Docs:    http://127.0.0.1:${HOST_PORT}/docs"
    echo "  Health:  http://127.0.0.1:${HOST_PORT}/api/health"
    echo "  Outputs: http://127.0.0.1:${HOST_PORT}/outputs/<request_id>/..."
    echo "=========================================="
    echo "  (replace 127.0.0.1 with your server IP if remote)"
    exit 0
  fi
  sleep 3
done

echo "Health check timeout. Recent logs:"
docker compose logs --tail=80
exit 1
