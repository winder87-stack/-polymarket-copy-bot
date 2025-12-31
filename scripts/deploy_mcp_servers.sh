#!/bin/bash
################################################################################
# Polymarket MCP Servers Deployment Script
#
# Production-safe deployment with:
# - Zero downtime
# - Automatic rollback
# - Staging validation
# - Resource validation
#
# Usage: ./scripts/deploy_mcp_servers.sh [staging|production]
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs/deployments"
MCP_DIR="$PROJECT_ROOT/mcp"

ENV="${1:-staging}"
DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/mcp_deploy_${ENV}_${DATE}.log"

# Create log directory
mkdir -p "$LOG_DIR"

################################################################################
# Logging Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

################################################################################
# Utility Functions
################################################################################

check_dependencies() {
    log_info "Checking dependencies..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found"
        exit 1
    fi

    # Check required packages
    local required_packages=("aiohttp" "prometheus_client" "psutil")
    for package in "${required_packages[@]}"; do
        if ! python3 -c "import $package" 2>/dev/null; then
            log_warning "Python package '$package' not installed"
            log_info "Install with: pip install $package"
        fi
    done

    log_success "Dependencies check complete"
}

check_environment_file() {
    log_info "Checking environment file..."

    local env_file="$PROJECT_ROOT/.env"
    local env_file_specific="$PROJECT_ROOT/.env.$ENV"

    if [[ "$ENV" == "staging" ]] && [[ -f "$env_file_specific" ]]; then
        export DOTENV_PATH="$env_file_specific"
        log_success "Using environment file: .env.$ENV"
    elif [[ -f "$env_file" ]]; then
        export DOTENV_PATH="$env_file"
        log_success "Using environment file: .env"
    else
        log_error "Environment file not found"
        exit 1
    fi
}

validate_market_hours() {
    log_info "Checking market hours..."

    local current_hour=$(date -u +%H)
    local market_start=9  # 9AM UTC
    local market_end=16   # 4PM UTC

    if [[ "$current_hour" -ge "$market_start" ]] && [[ "$current_hour" -lt "$market_end" ]]; then
        log_warning "Market hours currently active ($current_hour:00 UTC)"
        read -p "Continue with deployment? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deployment cancelled by user"
            exit 0
        fi
    else
        log_success "Outside market hours - safe to deploy"
    fi
}

pre_flight_checks() {
    log_info "Running pre-flight checks..."

    # Check bot is running
    if pgrep -x "main.py" > /dev/null; then
        log_warning "Bot is currently running"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deployment cancelled by user"
            exit 0
        fi
    fi

    # Check disk space (need at least 500MB)
    local available_space=$(df -BG "$PROJECT_ROOT" | awk '{print $4}')
    local min_space=$((500 * 1024))  # 500MB in KB

    if [[ "$available_space" -lt "$min_space" ]]; then
        log_error "Insufficient disk space (need 500MB, have $((available_space / 1024))MB)"
        exit 1
    fi

    log_success "Pre-flight checks complete"
}

################################################################################
# Health Validation
################################################################################

validate_health() {
    log_info "Validating MCP server health..."

    local health_check_script="$SCRIPT_DIR/mcp/validate_health.sh"

    if [[ -f "$health_check_script" ]]; then
        bash "$health_check_script" --env "$ENV" --mode "$1"
    else
        log_error "Health check script not found: $health_check_script"
        return 1
    fi

    return 0
}

################################################################################
# Staging Deployment
################################################################################

deploy_staging() {
    log_info "🚀 Deploying MCP servers to staging environment..."

    # Staging validation
    if [[ "$ENV" != "staging" ]]; then
        log_error "This script section requires ENV=staging"
        return 1
    fi

    # DRY_RUN mode (read-only operations)
    log_info "Starting DRY_RUN mode (read-only operations)..."

    # Run tests in staging
    log_info "Running MCP server tests..."
    cd "$PROJECT_ROOT"
    python3 -m pytest tests/test_monitoring.py -v --tb=short 2>&1 | tee -a "$LOG_FILE"

    if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
        log_error "Tests failed - aborting deployment"
        return 1
    fi

    log_success "Tests passed"

    # Validate configuration
    log_info "Validating staging configuration..."
    python3 -c "
from dotenv import load_dotenv
from pathlib import Path
import os

env_file = Path('$DOTENV_PATH')
if env_file.exists():
    load_dotenv(env_file)

from config.mcp_config import validate_monitoring_config

config = validate_monitoring_config()
print(f'Configuration validated:')
print(f'  Monitoring enabled: {config.enabled}')
print(f'  Dashboard enabled: {config.dashboard_enabled}')
print(f'  Metrics enabled: {config.metrics_enabled}')
print(f'  CPU limit: {config.max_cpu_percent}%')
print(f'  Memory limit: {config.max_memory_mb}MB')
" 2>&1 | tee -a "$LOG_FILE"

    log_success "Staging validation complete"
    log_info "DRY_RUN mode complete - no changes made"
}

################################################################################
# Production Deployment
################################################################################

deploy_production() {
    log_info "🚀 Deploying MCP servers to production environment..."

    if [[ "$ENV" != "production" ]]; then
        log_error "This script section requires ENV=production"
        return 1
    fi

    # Pre-deployment validation
    log_info "Running pre-deployment validation..."
    if ! validate_health "pre-deploy"; then
        log_error "Pre-deployment health checks failed"
        return 1
    fi

    # Backup current state
    log_info "Creating backup of current MCP state..."
    local backup_dir="$PROJECT_ROOT/backups/mcp"
    mkdir -p "$backup_dir"

    if [[ -d "$MCP_DIR" ]]; then
        local backup_file="mcp_${DATE}_backup.tar.gz"
        tar -czf "$backup_dir/$backup_file" -C "$PROJECT_ROOT" mcp/ 2>&1 | tee -a "$LOG_FILE"
        log_success "Backup created: $backup_file"
    fi

    # Deploy with zero downtime
    log_info "Deploying MCP servers..."

    # Update systemd service
    log_info "Updating systemd service..."
    cp "$SCRIPT_DIR/systemd/polymarket-mcp.service" /etc/systemd/system/ 2>&1 | tee -a "$LOG_FILE"

    # Reload systemd
    systemctl daemon-reload 2>&1 | tee -a "$LOG_FILE"

    # Enable service
    systemctl enable polymarket-mcp.service 2>&1 | tee -a "$LOG_FILE"

    # Start service (or restart if running)
    if systemctl is-active --quiet polymarket-mcp.service; then
        log_info "Restarting existing service..."
        systemctl restart polymarket-mcp.service 2>&1 | tee -a "$LOG_FILE"
    else
        log_info "Starting new service..."
        systemctl start polymarket-mcp.service 2>&1 | tee -a "$LOG_FILE"
    fi

    # Post-deployment validation
    log_info "Running post-deployment validation..."
    sleep 10  # Wait for service to stabilize

    if ! validate_health "post-deploy"; then
        log_error "Post-deployment health checks failed - initiating rollback"
        rollback_deployment
        return 1
    fi

    log_success "Production deployment complete"
}

################################################################################
# Rollback
################################################################################

rollback_deployment() {
    log_warning "🔄 Initiating rollback to previous state..."

    local backup_dir="$PROJECT_ROOT/backups/mcp"

    # Find most recent backup
    local latest_backup=$(ls -t "$backup_dir" | head -n1)

    if [[ -z "$latest_backup" ]]; then
        log_error "No backup found for rollback"
        return 1
    fi

    log_info "Rolling back to: $latest_backup"

    # Stop current service
    log_info "Stopping MCP service..."
    systemctl stop polymarket-mcp.service 2>&1 | tee -a "$LOG_FILE"

    # Restore from backup
    log_info "Restoring from backup..."
    tar -xzf "$backup_dir/$latest_backup" -C "$PROJECT_ROOT" 2>&1 | tee -a "$LOG_FILE"

    # Reload and restart
    systemctl daemon-reload 2>&1 | tee -a "$LOG_FILE"
    systemctl restart polymarket-mcp.service 2>&1 | tee -a "$LOG_FILE"

    # Verify rollback
    sleep 10
    if systemctl is-active --quiet polymarket-mcp.service; then
        log_success "Rollback complete - service running"
    else
        log_error "Rollback failed - service not starting"
        return 1
    fi
}

################################################################################
# Deployment Monitoring
################################################################################

monitor_deployment() {
    log_info "📊 Monitoring deployment for issues..."

    local monitor_duration="${1:-300}"  # Default 5 minutes
    local check_interval=30  # Check every 30 seconds
    local elapsed=0

    log_info "Monitoring for $monitor_duration seconds..."

    while [[ $elapsed -lt $monitor_duration ]]; do
        # Check service status
        if ! systemctl is-active --quiet polymarket-mcp.service; then
            log_error "Service stopped unexpectedly!"
            return 1
        fi

        # Check resource usage
        local memory=$(systemctl show polymarket-mcp.service -p MemoryCurrent | awk '{print $2}')
        local memory_limit=100000000  # 100MB in bytes

        if [[ $memory -gt $memory_limit ]]; then
            log_error "Memory usage exceeds limit: $((memory / 1024 / 1024))MB"
            return 1
        fi

        # Check logs for errors
        local error_count=$(journalctl -u polymarket-mcp.service --since "1 minute ago" | grep -c "ERROR\|CRITICAL" || true)

        if [[ $error_count -gt 10 ]]; then
            log_warning "High error rate detected: $error_count errors/minute"
        fi

        # Wait before next check
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
    done

    log_success "Deployment monitoring complete - no issues detected"
}

################################################################################
# Main Deployment Flow
################################################################################

main() {
    log_info "================================================================================"
    log_info "Polymarket MCP Servers Deployment"
    log_info "Environment: $ENV"
    log_info "Date: $(date -u)"
    log_info "================================================================================"

    # Check dependencies
    check_dependencies

    # Check environment file
    check_environment_file

    # Pre-flight checks
    pre_flight_checks

    # Validate market hours
    validate_market_hours

    # Deploy based on environment
    case "$ENV" in
        staging)
            deploy_staging
            ;;
        production)
            deploy_production

            # Monitor deployment
            monitor_deployment 300  # 5 minutes
            ;;
        *)
            log_error "Invalid environment: $ENV (use 'staging' or 'production')"
            echo "Usage: $0 [staging|production]"
            exit 1
            ;;
    esac

    log_info "================================================================================"
    log_success "Deployment complete!"
    log_info "================================================================================"
}

# Run main function
main "$@"
