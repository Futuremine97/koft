#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

./.venv/bin/pip install -r requirements.txt
exec ./.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8000}" --proxy-headers
