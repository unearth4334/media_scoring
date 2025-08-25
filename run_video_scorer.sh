#!/usr/bin/env sh
set -eu
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
. ".venv/bin/activate"
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null
eval "$( .venv/bin/python read_config.py --file config.yml --format sh )"
DIR="${1:-$DIR}"; PORT="${2:-$PORT}"; HOST="${HOST:-$HOST}"; STYLE="${STYLE:-$STYLE}"
echo "Starting Video Scorer: dir=$DIR  port=$PORT  host=$HOST  style=$STYLE"
exec python app.py --dir "$DIR" --port "$PORT" --host "$HOST" --style "$STYLE"
