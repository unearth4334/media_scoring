#!/bin/bash
# launch.sh - Media Scorer Container Management Script
# Manages Docker containers on QNAP NAS with proper PATH setup

set -e

# QNAP-specific configuration
QNAP_HOST="qnap"
QNAP_PATH="export PATH=\$PATH:/share/CACHEDEV1_DATA/.qpkg/container-station/bin:/usr/sbin:/sbin"
PROJECT_DIR="/share/Container/media_scoring"

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

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to execute commands on QNAP
execute_qnap_command() {
    local command="$1"
    print_status "Executing on QNAP: $command"
    ssh "$QNAP_HOST" "$QNAP_PATH; cd $PROJECT_DIR && $command"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [up|down|restart|status|logs] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  up       - Start the media scorer containers"
    echo "  down     - Stop the media scorer containers" 
    echo "  restart  - Restart the media scorer containers"
    echo "  status   - Show container status"
    echo "  logs     - Show container logs"
    echo "  destroy  - Stop containers and remove all volumes (DESTRUCTIVE)"
    echo ""
    echo "Options:"
    echo "  --build  - Force rebuild of containers (for up/restart)"
    echo "  --help   - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 up --build        # Start with fresh build"
    echo "  $0 down             # Stop containers"
    echo "  $0 restart --build  # Restart with rebuild"
    echo "  $0 destroy          # Stop and remove all data"
    echo "  $0 status           # Check container status"
    echo "  $0 logs             # View container logs"
}

# Function to start containers
start_containers() {
    local build_flag="$1"
    
    print_status "Starting Media Scorer containers..."
    
    if [[ "$build_flag" == "--build" ]]; then
        print_status "Building containers from scratch..."
        execute_qnap_command "docker compose up -d --build"
    else
        execute_qnap_command "docker compose up -d"
    fi
    
    print_success "Containers started successfully!"
    print_status "Web interface: http://10.0.78.66:7862"
    print_status "SSH access: ssh root@10.0.78.66 -p 2222"
}

# Function to stop containers
stop_containers() {
    print_status "Stopping Media Scorer containers..."
    execute_qnap_command "docker compose down"
    print_success "Containers stopped successfully!"
}

# Function to restart containers
restart_containers() {
    local build_flag="$1"
    
    print_status "Restarting Media Scorer containers..."
    stop_containers
    sleep 2
    start_containers "$build_flag"
}

# Function to show container status
show_status() {
    print_status "Container status:"
    execute_qnap_command "docker compose ps"
    echo ""
    print_status "All containers:"
    execute_qnap_command "docker ps -a"
}

# Function to show logs
show_logs() {
    print_status "Container logs:"
    execute_qnap_command "docker compose logs --tail=50"
}

# Function to destroy everything (containers + volumes)
destroy_all() {
    print_warning "⚠️  DESTRUCTIVE OPERATION ⚠️"
    print_warning "This will:"
    print_warning "  - Stop all containers"
    print_warning "  - Remove all volumes (database, scores, thumbnails, logs)"
    print_warning "  - Delete all stored data permanently"
    echo ""
    
    # Confirmation prompt
    read -p "Are you sure you want to destroy all data? Type 'yes' to continue: " -r
    echo ""
    
    if [[ $REPLY == "yes" ]]; then
        print_status "Destroying containers and volumes..."
        
        # Stop containers and remove volumes
        execute_qnap_command "docker compose down -v"
        
        # Remove any orphaned volumes
        print_status "Cleaning up orphaned volumes..."
        execute_qnap_command "docker volume prune -f"
        
        print_success "All containers and volumes destroyed!"
        print_status "You can now start fresh with: $0 up --build"
    else
        print_status "Operation cancelled."
        exit 0
    fi
}

# Main script logic
main() {
    # Check if SSH key is set up
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$QNAP_HOST" exit 2>/dev/null; then
        print_error "Cannot connect to QNAP host '$QNAP_HOST'"
        print_error "Ensure SSH key authentication is set up"
        exit 1
    fi
    
    case "${1:-help}" in
        "up")
            start_containers "$2"
            ;;
        "down") 
            stop_containers
            ;;
        "restart")
            restart_containers "$2"
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs
            ;;
        "destroy")
            destroy_all
            ;;
        "help"|"--help"|"-h"|"")
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
