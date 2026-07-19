#!/usr/bin/env bash
set -euo pipefail

# Activate virtual environment if it exists (created by START_HERE.py or manual setup).
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python -m app.main init-db
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
