#!/bin/sh
set -e

DATA_DIR="${DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR/outputs" "$DATA_DIR/uploads"

if [ ! -f "$DATA_DIR/jobs.json" ]; then
  printf '[]\n' > "$DATA_DIR/jobs.json"
fi

exec "$@"
