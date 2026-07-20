# Stamp AI Service - production image
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  # rembg model cache path (persist via volume)
  U2NET_HOME=/app/models/u2net \
  APP_PORT=8000 \
  APP_RELOAD=false \
  DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Optional: set at build time for China mirrors
#   docker compose build --build-arg APT_MIRROR=mirrors.aliyun.com
#   docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG APT_MIRROR=
ARG PIP_INDEX_URL=

# System deps for opencv / pillow / onnxruntime
# - Prefer APT_MIRROR when provided
# - Retry apt update (deb.debian.org often 502 on some networks)
# - bookworm-updates 502: fall back to main+security only
RUN set -eux; \
  if [ -n "${APT_MIRROR}" ]; then \
  sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
  if [ -f /etc/apt/sources.list ]; then \
  sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list; \
  fi; \
  fi; \
  for i in 1 2 3; do \
  apt-get update && break || sleep 3; \
  done; \
  apt-get install -y --no-install-recommends \
  libgl1 \
  libglib2.0-0 \
  libgomp1 \
  curl \
  ca-certificates \
  || { \
  echo "WARN: full apt install failed, retry without bookworm-updates..."; \
  if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
  sed -i '/bookworm-updates/d' /etc/apt/sources.list.d/debian.sources || true; \
  fi; \
  if [ -f /etc/apt/sources.list ]; then \
  sed -i '/bookworm-updates/d' /etc/apt/sources.list || true; \
  fi; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
  libgl1 \
  libglib2.0-0 \
  libgomp1 \
  curl \
  ca-certificates; \
  }; \
  rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN set -eux; \
  pip install --upgrade pip; \
  if [ -n "${PIP_INDEX_URL}" ]; then \
  pip install -r requirements.txt -i "${PIP_INDEX_URL}"; \
  pip uninstall -y opencv-python || true; \
  pip install "opencv-python-headless==4.10.0.84" -i "${PIP_INDEX_URL}"; \
  else \
  pip install -r requirements.txt; \
  pip uninstall -y opencv-python || true; \
  pip install "opencv-python-headless==4.10.0.84"; \
  fi

# App source (context is filtered by .dockerignore)
COPY . .

# Runtime dirs
RUN mkdir -p /app/uploads /app/outputs /app/logs /app/temp /app/models/u2net \
  && useradd --create-home --shell /bin/bash appuser \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${APP_PORT}/api/health" || exit 1

# Production: multi-worker uvicorn
CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${APP_PORT} --workers ${UVICORN_WORKERS:-2} --proxy-headers --forwarded-allow-ips='*'"]
