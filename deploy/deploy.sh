#!/usr/bin/env bash
# One-shot deploy helper for Stamp AI Service
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/6] Prepare dirs..."
mkdir -p data/uploads data/outputs data/logs data/temp data/models/u2net deploy/certs

if [[ ! -f .env ]]; then
  echo "[2/6] Create .env from .env.example"
  cp .env.example .env
else
  echo "[2/6] .env exists, skip"
fi

# Load .env for build args / ports
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env || true
  set +a
fi

export APT_MIRROR="${APT_MIRROR:-mirrors.aliyun.com}"
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"

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

echo "[4/6] Build images (no-cache recommended on first fixed build)..."
docker compose build --build-arg "APT_MIRROR=${APT_MIRROR}" --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL}"

echo "[5/6] Start services..."
docker compose up -d

echo "[6/6] Wait health..."
for i in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${HOST_PORT:-18080}/api/health" >/dev/null 2>&1 \
    || curl -fsS "http://127.0.0.1:${NGINX_HTTP_PORT:-18088}/api/health" >/dev/null 2>&1; then
    echo "Service is healthy."
    docker compose ps
    echo
    echo "Nginx:   http://<server-ip>:${NGINX_HTTP_PORT:-18088}/docs"
    echo "Health:  http://<server-ip>:${NGINX_HTTP_PORT:-18088}/api/health"
    echo "Direct:  http://<server-ip>:${HOST_PORT:-18080}/docs"
    exit 0
  fi
  sleep 3
done

echo "Health check timeout. Recent logs:"
docker compose logs --tail=80
exit 1
