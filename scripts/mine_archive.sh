#!/bin/bash

# Wrapper script for the data mining tool
# Makes it easier to use the mining tool with common options

# --- Resolve paths robustly ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Repo root is one level above scripts/
REPO_ROOT="$(realpath "$SCRIPT_DIR/..")"
VENV_DIR="$REPO_ROOT/.venv"
MINE_SCRIPT="$REPO_ROOT/tools/mine_data.py"
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
    echo "Media Archive Data Mining Tool"
    echo "=============================="
    echo ""
    echo "Usage: $0 <command> <directory> [options]"
    echo ""
    echo "Commands:"
    echo "  test <dir>       - Test directory scanning (dry run)"
    echo "  mine <dir>       - Mine data and store in database"
    echo "  quick <dir>      - Quick mine with default settings"
    echo "  images <dir>     - Mine only images (*.jpg|*.png|*.jpeg)"
    echo "  videos <dir>     - Mine only videos (*.mp4)"
    echo "  help             - Show this help"
    echo ""
    echo "Options:"
    echo "  --pattern <pat>  - File pattern (e.g., '*.mp4|*.png')"
    echo "  --db-path <path> - Custom database path"
    echo "  --verbose        - Enable verbose output"
    echo ""
    echo "Examples:"
    echo "  $0 test /media/archive1"
    echo "  $0 mine /media/archive1 --verbose"
    echo "  $0 images /media/photos"
    echo "  $0 videos /media/videos --db-path /custom/db.sqlite"
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

    # Validate mining script path
    if [[ ! -f "$MINE_SCRIPT" ]]; then
        print_error "Mining script not found: $MINE_SCRIPT"
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

    # Export for run_mining_tool
    export PYTHON_CMD="$PY"
    export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
}

run_mining_tool() {
    local args=("$@")
    local PY="${PYTHON_CMD:-$(resolve_python)}"
    print_status "Running: $PY $MINE_SCRIPT ${args[*]}"
    "$PY" "$MINE_SCRIPT" "${args[@]}"
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        print_success "Mining completed successfully!"
    else
        print_error "Mining failed with exit code $exit_code"
    fi
    return $exit_code
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
            echo "Usage: $0 test <directory> [--test-output-dir <dir>]"
            exit 1
        fi
        DIRECTORY="$1"; shift
        EXTRA_ARGS=()
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
                *)
                    EXTRA_ARGS+=("$1"); shift
                    ;;
            esac
        done
        print_status "Testing directory scan for: $DIRECTORY"
        check_environment
        run_mining_tool "$(realpath "$DIRECTORY")" --dry-run --verbose "${EXTRA_ARGS[@]}"
        ;;
    mine)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for mine command"
            echo "Usage: $0 mine <directory>"
            exit 1
        fi
        DIRECTORY="$(realpath "$1")"; shift
        print_status "Mining data from: $DIRECTORY"
        check_environment
        run_mining_tool "$DIRECTORY" --enable-database "$@"
        ;;
    quick)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for quick command"
            echo "Usage: $0 quick <directory>"
            exit 1
        fi
        DIRECTORY="$(realpath "$1")"; shift
        print_status "Quick mining from: $DIRECTORY"
        check_environment
        run_mining_tool "$DIRECTORY" --enable-database --pattern "*.mp4|*.png|*.jpg|*.jpeg" "$@"
        ;;
    images)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for images command"
            echo "Usage: $0 images <directory>"
            exit 1
        fi
        DIRECTORY="$(realpath "$1")"; shift
        print_status "Mining images from: $DIRECTORY"
        check_environment
        run_mining_tool "$DIRECTORY" --enable-database --pattern "*.jpg|*.png|*.jpeg" "$@"
        ;;
    videos)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for videos command"
            echo "Usage: $0 videos <directory>"
            exit 1
        fi
        DIRECTORY="$(realpath "$1")"; shift
        print_status "Mining videos from: $DIRECTORY"
        check_environment
        run_mining_tool "$DIRECTORY" --enable-database --pattern "*.mp4" "$@"
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        echo ""
        show_help
        exit 1
        ;;
esac
