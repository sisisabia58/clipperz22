FROM node:22-alpine AS frontend-deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS frontend-build
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE=
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
COPY --from=frontend-deps /app/node_modules ./node_modules
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      ffmpeg \
      fontconfig \
      fonts-dejavu-core \
      fonts-dejavu \
      fonts-liberation \
      fonts-noto-core \
      gettext-base \
      libglib2.0-0 \
      libgl1 \
      libgomp1 \
      nginx \
      supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node:22-alpine /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-alpine /usr/local/bin/npm /usr/local/bin/npm
COPY --from=node:22-alpine /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/bin/node /usr/bin/node \
    && ln -sf /usr/local/bin/npm /usr/bin/npm

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend-build /app/package.json /app/frontend/package.json
COPY --from=frontend-build /app/package-lock.json /app/frontend/package-lock.json
COPY --from=frontend-build /app/node_modules /app/frontend/node_modules
COPY --from=frontend-build /app/.next /app/frontend/.next
COPY --from=frontend-build /app/public /app/frontend/public
COPY --from=frontend-build /app/next.config.ts /app/frontend/next.config.ts

COPY deploy/railway/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY deploy/railway/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY deploy/railway/start.sh /start.sh
RUN chmod +x /start.sh \
    && mkdir -p /app/data/outputs /app/data/uploads

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8080\")}/api/health')"

CMD ["/start.sh"]
