#!/usr/bin/env sh
# Run Video Scorer (FastAPI) — POSIX shell entrypoint
# Usage:
#   ./run_video_scorer.sh [DIR] [PORT]
# Defaults:
#   DIR = current directory
#   PORT = 7862

set -eu

DIR="${1:-$(pwd)}"
PORT="${2:-7862}"
HOST="${HOST:-127.0.0.1}"

# Resolve script directory to locate project files
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create venv if missing
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# Activate venv
# shellcheck disable=SC1091
. ".venv/bin/activate"

# Upgrade pip quietly and install deps
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# Launch app
exec python app_fastapi.py --dir "$DIR" --port "$PORT" --host "$HOST"
