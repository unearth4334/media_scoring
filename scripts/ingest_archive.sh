#!/bin/bash

# Wrapper script for the data ingesting tool
# Makes it easier to use the ingesting tool with common options

set -euo pipefail

# --- Resolve paths robustly ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Repo root is one level above scripts/
REPO_ROOT="$(realpath "$SCRIPT_DIR/..")"
VENV_DIR="$REPO_ROOT/.venv"
INGEST_SCRIPT="$REPO_ROOT/tools/ingest_data.py"
REQ_FILE="$REPO_ROOT/requirements.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status()  { echo -e "${BLUE}[INFO]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

show_help() {
    echo "Media Archive Data Ingesting Tool"
    echo "=============================="
    echo ""
    echo "Usage: $0 <command> <directory> [options]"
    echo ""
    echo "Commands:"
    echo "  test <dir>       - Test directory scanning (dry run)"
    echo "  ingest <dir>     - Ingest data and store in database"
    echo "  quick <dir>      - Quick ingest with default settings"
    echo "  images <dir>     - Ingest only images (*.jpg|*.png|*.jpeg)"
    echo "  videos <dir>     - Ingest only videos (*.mp4)"
    echo "  help             - Show this help"
    echo ""
    echo "Options:"
    echo "  --pattern <pat>     - File pattern (e.g., '*.mp4|*.png')"
    echo "  --database-url <url> - PostgreSQL database URL (e.g., postgresql://user:pass@host/db)"
    echo "  --verbose           - Enable verbose output"
    echo "  --no-view           - (debug) bypass filtered symlink view"
    echo ""
    echo "Examples:"
    echo "  $0 test /media/archive1"
    echo "  $0 ingest /media/archive1 --verbose"
    echo "  $0 images /media/photos"
    echo "  $0 videos /media/videos --database-url postgresql://user:pass@host/db"
    echo ""
}

# Returns absolute path of first available python (pref venv)
resolve_python() {
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        echo "$VENV_DIR/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        echo "python3"
    else
        echo "python"
    fi
}

check_environment() {
    local PY
    # Activate venv if present
    if [[ -d "$VENV_DIR" ]]; then
        print_status "Activating Python virtual environment at $VENV_DIR..."
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
    else
        print_warning "No virtual environment found at $VENV_DIR. Using system Python."
    fi

    # Choose interpreter
    PY="$(resolve_python)"

    # Validate ingesting script path
    if [[ ! -f "$INGEST_SCRIPT" ]]; then
        print_error "Ingesting script not found: $INGEST_SCRIPT"
        exit 1
    fi

    # Validate imports by ensuring repo root is on sys.path
    if ! "$PY" - <<PYCODE 2>/dev/null
import sys, os
repo_root = os.path.abspath("$REPO_ROOT")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
from app.settings import Settings  # import check
print("ok")
PYCODE
    then
        print_error "Required Python modules not available or import path incorrect."
        if [[ -f "$REQ_FILE" ]]; then
            echo "  cd $REPO_ROOT && $(basename "$PY") -m pip install -r requirements.txt"
        else
            echo "  (No requirements.txt found at $REQ_FILE)"
        fi
        exit 1
    fi

    # Export for run_ingesting_tool
    export PYTHON_CMD="$PY"
    export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
}

run_ingesting_tool() {
    local args=("$@")
    local PY="${PYTHON_CMD:-$(resolve_python)}"
    print_status "Running: $PY $INGEST_SCRIPT ${args[*]}"
    "$PY" "$INGEST_SCRIPT" "${args[@]}"
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        print_success "Ingesting completed successfully!"
    else
        print_error "Ingesting failed with exit code $exit_code"
    fi
    return $exit_code
}

# --- Helpers to build a filtered symlink view that excludes caches/hidden ---

# Extracts a --pattern "*.ext|*.ext2|..." from argv and prints it; empty if none
extract_pattern_from_args() {
    local p=""
    local a
    for a in "$@"; do
        if [[ "$a" == --pattern ]]; then
            # next token is the value
            shift
            p="${1:-}"
            echo "$p"
            return
        fi
        shift || true
    done
    echo ""
}

# Converts shell-style pattern list to a find -iregex (e.g., "*.mp4|*.png" -> ".*\.\(mp4\|png\)$")
pattern_to_find_iregex() {
    local pat="$1"
    [[ -z "$pat" ]] && { echo ""; return; }
    # strip "*." from each, split on |
    local cleaned="${pat//\*\./}"        # "*.mp4|*.png" -> "mp4|png"
    cleaned="${cleaned//|/\\|}"          # "mp4|png" -> "mp4\|png"
    echo ".*\\.\\(${cleaned}\\)$"
}

# Build filtered symlink view under a temp dir; prints the temp path
# Skips hidden dirs (.*), and explicitly .thumbnails and .scores; optional -iregex to limit extensions
build_filtered_view() {
    local src="$1"; shift
    local iregex="$1"; shift || true

    local tmp
    tmp="$(mktemp -d -t ingestview.XXXXXX)"

    print_status "Creating filtered symlink view (hidden/.thumbnails/.scores excluded) ..."
    # Build find args array to avoid word-splitting trouble
    local -a find_tail
    if [[ -n "$iregex" ]]; then
        find_tail=(-type f -iregex "$iregex")
    else
        # Default: common media types if no pattern passed
        find_tail=(-type f -iregex '.*\.\(png\|jpg\|jpeg\|webp\|gif\|bmp\|tiff\|mp4\|mov\|mkv\|avi\)$')
    fi

    # Collect files and create parallel symlink tree
    while IFS= read -r -d '' f; do
        # rel path from src
        rel="${f#"$src"/}"
        mkdir -p "$tmp/$(dirname -- "$rel")"
        ln -s "$f" "$tmp/$rel"
    done < <(
        find "$src" \
            -type d \( -name '.*' -o -name '.thumbnails' -o -name '.scores' \) -prune -false -o \
            "${find_tail[@]}" \
            -print0 2>/dev/null
    )

    echo "$tmp"
}

# ---- CLI parsing ----
if [[ $# -eq 0 ]]; then
    show_help
    exit 1
fi

COMMAND="$1"; shift

case "$COMMAND" in
    help|--help|-h)
        show_help
        exit 0
        ;;

    test)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for test command"
            echo "Usage: $0 test <directory> [--test-output-dir <dir>] [--no-view]"
            exit 1
        fi
        DIRECTORY="$1"; shift
        EXTRA_ARGS=()
        NO_VIEW=0
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --test-output-dir)
                    EXTRA_ARGS+=("$1"); shift
                    if [[ $# -gt 0 ]]; then
                        EXTRA_ARGS+=("$(realpath "$1")"); shift
                    else
                        print_error "--test-output-dir requires a value"
                        exit 1
                    fi
                    ;;
                --no-view)
                    NO_VIEW=1; shift ;;
                *)
                    EXTRA_ARGS+=("$1"); shift ;;
            esac
        done
        DIRECTORY="$(realpath "$DIRECTORY")"
        print_status "Testing directory scan for: $DIRECTORY"
        check_environment
        if [[ $NO_VIEW -eq 1 ]]; then
            run_ingesting_tool "$DIRECTORY" --dry-run --verbose "${EXTRA_ARGS[@]}"
        else
            local_pattern="$(extract_pattern_from_args "${EXTRA_ARGS[@]}")"
            local_regex="$(pattern_to_find_iregex "$local_pattern")"
            VIEW_DIR="$(build_filtered_view "$DIRECTORY" "$local_regex")"
            trap 'rm -rf "$VIEW_DIR"' EXIT
            run_ingesting_tool "$VIEW_DIR" --dry-run --verbose "${EXTRA_ARGS[@]}"
        fi
        ;;

    ingest)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for ingest command"
            echo "Usage: $0 ingest <directory> [options] [--no-view]"
            exit 1
        fi
        DIRECTORY="$(realpath "$1")"; shift
        NO_VIEW=0
        # pass-through args; strip --no-view if present
        PASS_ARGS=()
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --no-view) NO_VIEW=1; shift ;;
                *) PASS_ARGS+=("$1"); shift ;;
            esac
        done
        print_status "Ingesting data from: $DIRECTORY"
        check_environment
        if [[ $NO_VIEW -eq 1 ]]; then
            run_ingesting_tool "$DIRECTORY" --enable-database "${PASS_ARGS[@]}"
        else
            local_pattern="$(extract_pattern_from_args "${PASS_ARGS[@]}")"
            local_regex="$(pattern_to_find_iregex "$local_pattern")"
            VIEW_DIR="$(build_filtered_view "$DIRECTORY" "$local_regex")"
            trap 'rm -rf "$VIEW_DIR"' EXIT
            run_ingesting_tool "$VIEW_DIR" --enable-database "${PASS_ARGS[@]}"
        fi
        ;;

    mine)
        # Backward compatibility - redirect to ingest
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for mine command"
            echo "Usage: $0 mine <directory> (Note: 'mine' is deprecated, use 'ingest')"
            exit 1
        fi
        DIRECTORY="$(realpath "$1")"; shift
        print_warning "The 'mine' command is deprecated. Please use 'ingest' instead."
        print_status "Ingesting data from: $DIRECTORY"
        check_environment
        local_pattern="$(extract_pattern_from_args "$@")"
        local_regex="$(pattern_to_find_iregex "$local_pattern")"
        VIEW_DIR="$(build_filtered_view "$DIRECTORY" "$local_regex")"
        trap 'rm -rf "$VIEW_DIR"' EXIT
        run_ingesting_tool "$VIEW_DIR" --enable-database "$@"
        ;;

    quick)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for quick command"
            echo "Usage: $0 quick <directory> [--no-view]"
            exit 1
        fi
        DIRECTORY="$(realpath "$1")"; shift
        NO_VIEW=0
        PASS_ARGS=()
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --no-view) NO_VIEW=1; shift ;;
                *) PASS_ARGS+=("$1"); shift ;;
            esac
        done
        print_status "Quick ingesting from: $DIRECTORY"
        check_environment
        if [[ $NO_VIEW -eq 1 ]]; then
            run_ingesting_tool "$DIRECTORY" --enable-database --pattern "*.mp4|*.png|*.jpg|*.jpeg" "${PASS_ARGS[@]}"
        else
            local_regex="$(pattern_to_find_iregex "*.mp4|*.png|*.jpg|*.jpeg")"
            VIEW_DIR="$(build_filtered_view "$DIRECTORY" "$local_regex")"
            trap 'rm -rf "$VIEW_DIR"' EXIT
            run_ingesting_tool "$VIEW_DIR" --enable-database --pattern "*.mp4|*.png|*.jpg|*.jpeg" "${PASS_ARGS[@]}"
        fi
        ;;

    images)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for images command"
            echo "Usage: $0 images <directory> [--no-view]"
            exit 1
        fi
        DIRECTORY="$(realpath "$1")"; shift
        NO_VIEW=0
        PASS_ARGS=()
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --no-view) NO_VIEW=1; shift ;;
                *) PASS_ARGS+=("$1"); shift ;;
            esac
        done
        print_status "Ingesting images from: $DIRECTORY"
        check_environment
        if [[ $NO_VIEW -eq 1 ]]; then
            run_ingesting_tool "$DIRECTORY" --enable-database --pattern "*.jpg|*.png|*.jpeg" "${PASS_ARGS[@]}"
        else
            local_regex="$(pattern_to_find_iregex "*.jpg|*.png|*.jpeg")"
            VIEW_DIR="$(build_filtered_view "$DIRECTORY" "$local_regex")"
            trap 'rm -rf "$VIEW_DIR"' EXIT
            run_ingesting_tool "$VIEW_DIR" --enable-database --pattern "*.jpg|*.png|*.jpeg" "${PASS_ARGS[@]}"
        fi
        ;;

    videos)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for videos command"
            echo "Usage: $0 videos <directory> [--no-view]"
            exit 1
        fi
        DIRECTORY="$(realpath "$1")"; shift
        NO_VIEW=0
        PASS_ARGS=()
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --no-view) NO_VIEW=1; shift ;;
                *) PASS_ARGS+=("$1"); shift ;;
            esac
        done
        print_status "Ingesting videos from: $DIRECTORY"
        check_environment
        if [[ $NO_VIEW -eq 1 ]]; then
            run_ingesting_tool "$DIRECTORY" --enable-database --pattern "*.mp4" "${PASS_ARGS[@]}"
        else
            local_regex="$(pattern_to_find_iregex "*.mp4")"
            VIEW_DIR="$(build_filtered_view "$DIRECTORY" "$local_regex")"
            trap 'rm -rf "$VIEW_DIR"' EXIT
            run_ingesting_tool "$VIEW_DIR" --enable-database --pattern "*.mp4" "${PASS_ARGS[@]}"
        fi
        ;;

    *)
        print_error "Unknown command: $COMMAND"
        echo ""
        show_help
        exit 1
        ;;
esac