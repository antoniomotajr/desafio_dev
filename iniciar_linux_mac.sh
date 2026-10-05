#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

"$PYTHON" -c "import flask, waitress" >/dev/null 2>&1 || \
  "$PYTHON" -m pip install -r requirements.txt

export MOTA_ALLOW_LAN="${MOTA_ALLOW_LAN:-0}"
exec "$PYTHON" app.py
