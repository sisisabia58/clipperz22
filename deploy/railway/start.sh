#!/bin/sh
set -e

export PORT="${PORT:-8080}"
export DATA_DIR="${DATA_DIR:-/app/data}"

mkdir -p "$DATA_DIR/outputs" "$DATA_DIR/uploads"
if [ ! -f "$DATA_DIR/jobs.json" ]; then
  printf '[]\n' > "$DATA_DIR/jobs.json"
fi

envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
