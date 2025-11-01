#!/usr/bin/env bash
set -euo pipefail

cd /app
poetry run cad-service "$@"
