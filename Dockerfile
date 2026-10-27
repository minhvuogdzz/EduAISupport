# syntax=docker/dockerfile:1
# CAVAT AI Tutor: one image, one port. The API serves the web app it was built with (ADR-035, ADR-036).
# Build and run it with docker compose (deploy/README.md), not by hand.

# --- 1. The web app (React + Vite). VITE_API=http: the browser calls the API at the address it was opened from.
FROM node:22-bookworm-slim AS web
RUN corepack enable
WORKDIR /build
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web/ ./
RUN VITE_API=http pnpm build

# --- 2. The API (Python), with the build of the web app next to it.
FROM python:3.11-slim-bookworm AS app
ARG CAVAT_REVISION=unknown
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    CAVAT_REVISION=$CAVAT_REVISION
LABEL org.opencontainers.image.revision=$CAVAT_REVISION
WORKDIR /app

# The code finds its lessons and the web build relative to its own folder (REPO_ROOT in cavat/config.py), so the
# layout of the repository is kept: /app/services/api, /app/docs/pedagogy, /app/apps/web/dist. An editable
# install keeps the package where it is.
COPY services/api /app/services/api
RUN pip install -e /app/services/api
COPY docs/pedagogy /app/docs/pedagogy
COPY --from=web /build/dist /app/apps/web/dist
COPY --chmod=0755 deploy/entrypoint.sh /usr/local/bin/cavat-entrypoint

# Not root. /data/storage holds the library's original files and the audio (a named volume in compose).
RUN useradd --system --create-home --uid 10001 cavat \
 && mkdir -p /data/storage \
 && chown cavat:cavat /data/storage
ENV STORAGE_DIR=/data/storage
USER cavat
WORKDIR /app/services/api

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/db', timeout=4)"

# One process on purpose: the login lockout and the quota tracker live in its memory.
ENTRYPOINT ["cavat-entrypoint"]
CMD ["uvicorn", "cavat.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--proxy-headers", "--forwarded-allow-ips", "*"]
