#!/usr/bin/env bash
# FootFit AI 실행 스크립트
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -r requirements.txt
fi

echo "→ http://localhost:8000"
./.venv/bin/uvicorn backend.main:app --reload --port 8000
