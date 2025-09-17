#!/bin/bash

# Wrapper script for the data mining tool
# Makes it easier to use the mining tool with common options

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MINE_SCRIPT="$SCRIPT_DIR/../tools/mine_data.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to show help
show_help() {
    echo "Media Archive Data Mining Tool"
    echo "=============================="
    echo ""
    echo "This script helps you extract metadata from media archives and store it in the database."
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

# Check if Python virtual environment is available
check_environment() {
    if [[ -d "$SCRIPT_DIR/../.venv" ]]; then
        print_status "Activating Python virtual environment..."
        source "$SCRIPT_DIR/../.venv/bin/activate"
    else
        print_warning "No virtual environment found. Using system Python."
    fi
    
    # Check if the mining script exists
    if [[ ! -f "$MINE_SCRIPT" ]]; then
        print_error "Mining script not found: $MINE_SCRIPT"
        exit 1
    fi
    
    # Check if Python and required modules are available
    if ! python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from app.settings import Settings" 2>/dev/null; then
        print_error "Required Python modules not available. Please install dependencies:"
        echo "  cd $SCRIPT_DIR && pip install -r requirements.txt"
        exit 1
    fi
}

# Function to run the mining tool
run_mining_tool() {
    local args=("$@")
    print_status "Running: python3 $MINE_SCRIPT ${args[*]}"
    python3 "$MINE_SCRIPT" "${args[@]}"
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        print_success "Mining completed successfully!"
    else
        print_error "Mining failed with exit code $exit_code"
    fi
    
    return $exit_code
}

# Parse command line arguments
if [[ $# -eq 0 ]]; then
    show_help
    exit 1
fi

COMMAND="$1"
shift

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
        DIRECTORY="$1"
        shift
        # Collect all remaining args
        EXTRA_ARGS=()
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --test-output-dir)
                    EXTRA_ARGS+=("$1")
                    shift
                    if [[ $# -gt 0 ]]; then
                        EXTRA_ARGS+=("$1")
                        shift
                    else
                        print_error "--test-output-dir requires a value"
                        exit 1
                    fi
                    ;;
                *)
                    EXTRA_ARGS+=("$1")
                    shift
                    ;;
            esac
        done
        print_status "Testing directory scan for: $DIRECTORY"
        check_environment
        run_mining_tool "$DIRECTORY" --dry-run --verbose "${EXTRA_ARGS[@]}"
        ;;
    mine)
        if [[ $# -eq 0 ]]; then
            print_error "Directory required for mine command"
            echo "Usage: $0 mine <directory>"
            exit 1
        fi
        DIRECTORY="$1"
        shift
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
        DIRECTORY="$1"
        shift
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
        DIRECTORY="$1"
        shift
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
        DIRECTORY="$1"
        shift
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