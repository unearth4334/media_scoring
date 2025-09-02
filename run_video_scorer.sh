#!/usr/bin/env sh
set -eu
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
. ".venv/bin/activate"
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null
eval "$( .venv/bin/python read_config.py --file config.yml --format sh )"
DIR="${1:-$DIR}"; PORT="${2:-$PORT}"; HOST="${HOST:-$HOST}"; PATTERN="${3:-$PATTERN}"; STYLE="${STYLE:-$STYLE}"
# Parse toggle extensions from JSON array format
TOGGLE_EXT_LIST=$(echo "$TOGGLE_EXTENSIONS" | sed 's/\[//g' | sed 's/\]//g' | sed 's/"//g' | sed 's/,/ /g')
echo "Starting Video Scorer: dir=$DIR  port=$PORT  host=$HOST  pattern=$PATTERN  style=$STYLE  thumbnails=$GENERATE_THUMBNAILS  thumb_height=$THUMBNAIL_HEIGHT  toggle_ext=$TOGGLE_EXT_LIST  dir_sort_desc=$DIRECTORY_SORT_DESC"
THUMBNAIL_ARGS=""
if [ "$GENERATE_THUMBNAILS" = "true" ]; then
    THUMBNAIL_ARGS="--generate-thumbnails --thumbnail-height $THUMBNAIL_HEIGHT"
fi
DIRECTORY_SORT_ARGS=""
if [ "$DIRECTORY_SORT_DESC" = "false" ]; then
    DIRECTORY_SORT_ARGS="--directory-sort-asc"
fi
exec python run.py --dir "$DIR" --port "$PORT" --host "$HOST" --pattern "$PATTERN" --style "$STYLE" $THUMBNAIL_ARGS --toggle-extensions $TOGGLE_EXT_LIST $DIRECTORY_SORT_ARGS
