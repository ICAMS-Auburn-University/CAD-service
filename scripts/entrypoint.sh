#!/usr/bin/env bash

set -euo pipefail

cd /app

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

PORT="${PORT:-8000}"

exec poetry run uvicorn app:app --host 0.0.0.0 --port "$PORT"
