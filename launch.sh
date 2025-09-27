#!/bin/bash
# launch.sh - Media Scorer Container Management Script
# Manages Docker containers on QNAP NAS with proper PATH setup

set -e

# QNAP-specific configuration
QNAP_HOST="qnap"
QNAP_PATH="export PATH=\$PATH:/share/CACHEDEV1_DATA/.qpkg/container-station/bin:/usr/sbin:/sbin"
PROJECT_DIR="/share/Container/media_scoring"

# Colors for beautiful output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# Function to print colored output with emojis
print_header() {
    echo -e "\n${BOLD}${PURPLE}🚀 Media Scorer Container Manager${NC}"
    echo -e "${GRAY}═══════════════════════════════════${NC}\n"
}

print_status() {
    echo -e "${BLUE}ℹ️  [INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ [SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️  [WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}❌ [ERROR]${NC} $1"
}

print_command() {
    echo -e "${CYAN}▶️  Executing:${NC} ${DIM}$1${NC}"
}

print_separator() {
    echo -e "${GRAY}────────────────────────────────────${NC}"
}

# Function to execute commands on QNAP
execute_qnap_command() {
    local command="$1"
    print_command "$command"
    ssh "$QNAP_HOST" "$QNAP_PATH; cd $PROJECT_DIR && $command"
}

# Function to show usage
show_usage() {
    print_header
    
    echo -e "${BOLD}Usage:${NC} ${WHITE}$0${NC} ${CYAN}[COMMAND]${NC} ${YELLOW}[OPTIONS]${NC}"
    echo ""
    
    echo -e "${BOLD}📋 Commands:${NC}"
    echo -e "  ${GREEN}up${NC}       🚀 Start the media scorer containers"
    echo -e "  ${RED}down${NC}     ⏹️  Stop the media scorer containers" 
    echo -e "  ${YELLOW}restart${NC}  🔄 Restart the media scorer containers"
    echo -e "  ${BLUE}status${NC}   📊 Show container status"
    echo -e "  ${PURPLE}logs${NC}     📋 Show container logs"
    echo -e "  ${RED}destroy${NC}  💥 Stop containers and remove all volumes ${RED}(DESTRUCTIVE)${NC}"
    echo ""
    
    echo -e "${BOLD}⚙️  Options:${NC}"
    echo -e "  ${CYAN}--build${NC}  🔨 Force rebuild of containers (for up/restart)"
    echo -e "  ${CYAN}--help${NC}   ❓ Show this help message"
    echo ""
    
    echo -e "${BOLD}💡 Examples:${NC}"
    echo -e "  ${DIM}$0${NC} ${GREEN}up${NC} ${CYAN}--build${NC}        ${GRAY}# Start with fresh build${NC}"
    echo -e "  ${DIM}$0${NC} ${RED}down${NC}             ${GRAY}# Stop containers${NC}"
    echo -e "  ${DIM}$0${NC} ${YELLOW}restart${NC} ${CYAN}--build${NC}  ${GRAY}# Restart with rebuild${NC}"
    echo -e "  ${DIM}$0${NC} ${RED}destroy${NC}          ${GRAY}# Stop and remove all data${NC}"
    echo -e "  ${DIM}$0${NC} ${BLUE}status${NC}           ${GRAY}# Check container status${NC}"
    echo -e "  ${DIM}$0${NC} ${PURPLE}logs${NC}             ${GRAY}# View container logs${NC}"
    
    print_separator
}

# Function to start containers
start_containers() {
    local build_flag="$1"
    
    print_header
    print_status "🚀 Starting Media Scorer containers..."
    print_separator
    
    if [[ "$build_flag" == "--build" ]]; then
        print_status "🔨 Building containers from scratch..."
        execute_qnap_command "docker compose up -d --build"
    else
        execute_qnap_command "docker compose up -d"
    fi
    
    print_separator
    print_success "🎉 Containers started successfully!"
    echo ""
    echo -e "${BOLD}🌐 Access Points:${NC}"
    echo -e "  ${CYAN}Web Interface:${NC} ${WHITE}http://10.0.78.66:7862${NC}"
    echo -e "  ${CYAN}SSH Access:${NC}    ${WHITE}ssh root@10.0.78.66 -p 2222${NC}"
    print_separator
}

# Function to stop containers
stop_containers() {
    print_header
    print_status "⏹️  Stopping Media Scorer containers..."
    print_separator
    execute_qnap_command "docker compose down"
    print_separator
    print_success "🛑 Containers stopped successfully!"
}

# Function to restart containers
restart_containers() {
    local build_flag="$1"
    
    print_header
    print_status "🔄 Restarting Media Scorer containers..."
    print_separator
    
    print_status "⏹️  Stopping containers first..."
    execute_qnap_command "docker compose down"
    
    print_status "⏳ Waiting 2 seconds..."
    sleep 2
    
    print_status "🚀 Starting containers..."
    if [[ "$build_flag" == "--build" ]]; then
        print_status "🔨 Building containers from scratch..."
        execute_qnap_command "docker compose up -d --build"
    else
        execute_qnap_command "docker compose up -d"
    fi
    
    print_separator
    print_success "🎉 Containers restarted successfully!"
    echo ""
    echo -e "${BOLD}🌐 Access Points:${NC}"
    echo -e "  ${CYAN}Web Interface:${NC} ${WHITE}http://10.0.78.66:7862${NC}"
    echo -e "  ${CYAN}SSH Access:${NC}    ${WHITE}ssh root@10.0.78.66 -p 2222${NC}"
    print_separator
}

# Function to show container status
show_status() {
    print_header
    print_status "📊 Checking container status..."
    print_separator
    
    echo -e "${BOLD}🐳 Media Scorer Containers:${NC}"
    execute_qnap_command "docker compose ps"
    
    echo -e "\n${BOLD}🔍 All Containers on Host:${NC}"
    execute_qnap_command "docker ps -a"
    print_separator
}

# Function to show logs
show_logs() {
    print_header
    print_status "📋 Fetching container logs..."
    print_separator
    
    echo -e "${BOLD}📜 Recent Container Logs (last 50 lines):${NC}"
    execute_qnap_command "docker compose logs --tail=50"
    print_separator
}

# Function to destroy everything (containers + volumes)
destroy_all() {
    print_header
    
    echo -e "${BOLD}${RED}💥 DESTRUCTIVE OPERATION WARNING 💥${NC}\n"
    
    echo -e "${RED}⚠️  This will permanently delete:${NC}"
    echo -e "  ${RED}•${NC} Stop all containers"
    echo -e "  ${RED}•${NC} Remove all volumes (database, scores, thumbnails, logs)"
    echo -e "  ${RED}•${NC} Delete all stored data permanently"
    echo -e "  ${RED}•${NC} Clean up orphaned volumes"
    
    print_separator
    
    # Confirmation prompt
    echo -e "${YELLOW}💭 Are you absolutely sure?${NC}"
    read -p "$(echo -e "${BOLD}Type 'yes' to continue with destruction:${NC} ")" -r
    echo ""
    
    if [[ $REPLY == "yes" ]]; then
        print_separator
        print_status "💥 Destroying containers and volumes..."
        
        # Stop containers and remove volumes
        execute_qnap_command "docker compose down -v"
        
        # Remove any orphaned volumes
        print_status "🧹 Cleaning up orphaned volumes..."
        execute_qnap_command "docker volume prune -f"
        
        print_separator
        print_success "💀 All containers and volumes destroyed!"
        echo ""
        echo -e "${BOLD}🔄 To start fresh:${NC}"
        echo -e "  ${DIM}$0${NC} ${GREEN}up${NC} ${CYAN}--build${NC}"
        print_separator
    else
        print_status "🚫 Operation cancelled - your data is safe!"
        exit 0
    fi
}

# Main script logic
main() {
    # Check if SSH key is set up
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$QNAP_HOST" exit 2>/dev/null; then
        print_header
        print_error "🔌 Cannot connect to QNAP host '$QNAP_HOST'"
        print_error "🔑 Ensure SSH key authentication is set up"
        print_separator
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
            print_header
            print_error "❓ Unknown command: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
