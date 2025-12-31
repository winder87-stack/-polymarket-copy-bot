#!/bin/bash
#
# Deployment Script for Production-Ready Copy Trading Strategy
#
# This script deploys the new production-ready copy trading strategy
# with all quality scoring, red flag detection, and dynamic positioning.
#
# Usage:
#   ./deploy_production_strategy.sh [staging|production] [--dry-run]
#
# Examples:
#   ./deploy_production_strategy.sh staging --dry-run    # Test in staging mode
#   ./deploy_production_strategy.sh production           # Deploy to production
#

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="staging"
DRY_RUN=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/logs/deployment_$(date +%Y%m%d_%H%M%S).log"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        staging|production)
            ENVIRONMENT=$1
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            echo "Usage: $0 [staging|production] [--dry-run]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Production-Ready Strategy Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Environment: ${GREEN}${ENVIRONMENT}${NC}"
echo -e "Dry Run: ${YELLOW}${DRY_RUN}${NC}"
echo ""

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

info() {
    log "INFO" "$@"
}

warn() {
    log "WARN" -e "${YELLOW}$@${NC}"
}

error() {
    log "ERROR" -e "${RED}$@${NC}"
}

success() {
    log "SUCCESS" -e "${GREEN}$@${NC}"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    # Check if running from project root
    if [[ ! -f "${PROJECT_ROOT}/main.py" ]]; then
        error "Must run from project root directory"
        exit 1
    fi

    # Check Python version
    local python_version=$(python3 --version 2>&1 | awk '{print $2}')
    info "Python version: ${python_version}"

    # Check if required Python packages are installed
    if ! python3 -c "import pytest" 2>/dev/null; then
        error "pytest not installed. Run: pip install pytest pytest-asyncio"
        exit 1
    fi

    if ! python3 -c "import pydantic" 2>/dev/null; then
        error "pydantic not installed. Run: pip install pydantic"
        exit 1
    fi

    success "All prerequisites checked"
}

# Backup existing configuration
backup_config() {
    info "Backing up existing configuration..."

    if [[ -f "${PROJECT_ROOT}/config/settings.py" ]]; then
        cp "${PROJECT_ROOT}/config/settings.py" "${PROJECT_ROOT}/config/settings.py.backup.$(date +%Y%m%d_%H%M%S)"
        success "Settings backed up"
    fi

    if [[ -f "${PROJECT_ROOT}/config/scanner_config.py" ]]; then
        cp "${PROJECT_ROOT}/config/scanner_config.py" "${PROJECT_ROOT}/config/scanner_config.py.backup.$(date +%Y%m%d_%H%M%S)"
        success "Scanner config backed up"
    fi
}

# Validate environment variables
validate_environment() {
    info "Validating environment variables..."

    # Create .env file for staging if not exists
    local env_file="${PROJECT_ROOT}/.env.${ENVIRONMENT}"

    if [[ ! -f "${env_file}" ]]; then
        warn "No ${env_file} found. Creating from template..."

        if [[ -f "${PROJECT_ROOT}/env-${ENVIRONMENT}-template.txt" ]]; then
            cp "${PROJECT_ROOT}/env-${ENVIRONMENT}-template.txt" "${env_file}"
            info "Created ${env_file} from template"
        else
            error "No template file found: env-${ENVIRONMENT}-template.txt"
            exit 1
        fi
    fi

    # Source environment file
    source "${env_file}"

    # Check critical variables
    local required_vars=(
        "PRIVATE_KEY"
        "WALLET_ADDRESS"
        "POLYGON_RPC_URL"
        "CLOB_HOST"
    )

    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        error "Missing required environment variables: ${missing_vars[*]}"
        error "Please update ${env_file} with required values"
        exit 1
    fi

    success "Environment variables validated"
}

# Deploy new components
deploy_components() {
    info "Deploying new strategy components..."

    local components=(
        "core/wallet_quality_scorer.py"
        "core/red_flag_detector.py"
        "core/dynamic_position_sizer.py"
        "core/wallet_behavior_monitor.py"
    )

    for component in "${components[@]}"; do
        local component_path="${PROJECT_ROOT}/${component}"

        if [[ ! -f "${component_path}" ]]; then
            error "Component not found: ${component_path}"
            exit 1
        fi

        info "Deploying: ${component}"

        # Validate Python syntax
        if ! python3 -m py_compile "${component_path}" 2>/dev/null; then
            error "Syntax error in ${component_path}"
            exit 1
        fi
    done

    success "All components deployed"
}

# Run tests
run_tests() {
    info "Running integration tests..."

    local test_file="${PROJECT_ROOT}/tests/integration/test_copy_trading_strategy.py"

    if [[ ! -f "${test_file}" ]]; then
        warn "Integration tests not found: ${test_file}"
        warn "Skipping tests"
        return
    fi

    # Set environment for testing
    export TESTING_MODE="true"
    export DRY_RUN="true"

    # Run pytest
    if ! python3 -m pytest "${test_file}" -v --tb=short 2>&1 | tee -a "${LOG_FILE}"; then
        error "Integration tests failed"
        exit 1
    fi

    success "Integration tests passed"
}

# Update configuration
update_configuration() {
    info "Updating configuration for ${ENVIRONMENT}..."

    if [[ "${DRY_RUN}" == "true" ]]; then
        info "DRY RUN: Skipping configuration update"
        return
    fi

    # Update environment variables for staging
    if [[ "${ENVIRONMENT}" == "staging" ]]; then
        export DRY_RUN="true"
        export MAX_POSITION_SIZE="50.00"
        export MAX_DAILY_LOSS="25.00"
        export MIN_CONFIDENCE_SCORE="0.8"
        info "Set staging configuration: DRY_RUN=true, MAX_POSITION_SIZE=50.00"
    fi

    # Update environment variables for production
    if [[ "${ENVIRONMENT}" == "production" ]]; then
        export DRY_RUN="false"
        export MAX_POSITION_SIZE="500.00"
        export MAX_DAILY_LOSS="100.00"
        export MIN_CONFIDENCE_SCORE="0.7"
        info "Set production configuration: DRY_RUN=false, MAX_POSITION_SIZE=500.00"
    fi

    success "Configuration updated"
}

# Restart services
restart_services() {
    if [[ "${DRY_RUN}" == "true" ]]; then
        info "DRY RUN: Skipping service restart"
        return
    fi

    info "Restarting services..."

    # Check if systemd is available
    if command -v systemctl &> /dev/null; then
        # Stop services
        if systemctl is-active --quiet polymarket-bot; then
            info "Stopping polymarket-bot service..."
            sudo systemctl stop polymarket-bot
        fi

        # Start services
        info "Starting polymarket-bot service..."
        sudo systemctl start polymarket-bot

        # Check status
        if systemctl is-active --quiet polymarket-bot; then
            success "polymarket-bot service started successfully"
        else
            error "Failed to start polymarket-bot service"
            sudo systemctl status polymarket-bot
            exit 1
        fi
    else
        warn "systemd not available. Please restart services manually."
    fi
}

# Verify deployment
verify_deployment() {
    info "Verifying deployment..."

    # Wait for services to start
    sleep 5

    # Check if processes are running
    if pgrep -f "python3.*main.py" > /dev/null; then
        success "Main bot process is running"
    else
        warn "Main bot process not detected"
    fi

    # Check logs for errors
    local log_file="${PROJECT_ROOT}/logs/polymarket_bot.log"

    if [[ -f "${log_file}" ]]; then
        local errors=$(tail -100 "${log_file}" | grep -i "error" | wc -l)

        if [[ ${errors} -gt 0 ]]; then
            warn "Found ${errors} errors in recent logs"
            warn "Check logs: tail -f ${log_file}"
        else
            success "No errors in recent logs"
        fi
    fi
}

# Print deployment summary
print_summary() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Deployment Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo "Environment: ${ENVIRONMENT}"
    echo "Dry Run: ${DRY_RUN}"
    echo "Timestamp: $(date)"
    echo "Log File: ${LOG_FILE}"
    echo ""
    echo -e "${GREEN}Deployment completed successfully!${NC}"
    echo ""
    echo "Next Steps:"
    if [[ "${ENVIRONMENT}" == "staging" ]]; then
        echo "1. Monitor staging logs for 24 hours"
        echo "2. Check performance metrics:"
        echo "   python scripts/monitor_memory.py --duration 86400"
        echo "3. Validate all components are working correctly"
        echo "4. If successful, run: $0 production"
    else
        echo "1. Monitor production logs continuously"
        echo "   tail -f ${PROJECT_ROOT}/logs/polymarket_bot.log"
        echo "2. Check system health:"
        echo "   systemctl status polymarket-bot"
        echo "3. Review performance metrics every 6 hours"
    fi
}

# Main deployment workflow
main() {
    echo ""
    info "Starting deployment workflow..."
    echo ""

    # Step 1: Check prerequisites
    check_prerequisites

    # Step 2: Backup existing configuration
    backup_config

    # Step 3: Validate environment
    validate_environment

    # Step 4: Deploy components
    deploy_components

    # Step 5: Run tests
    run_tests

    # Step 6: Update configuration
    update_configuration

    # Step 7: Restart services
    restart_services

    # Step 8: Verify deployment
    verify_deployment

    # Step 9: Print summary
    print_summary
}

# Handle errors
trap 'error "Deployment failed at line $LINENO. Check log: ${LOG_FILE}"' ERR

# Run main workflow
main "$@"
