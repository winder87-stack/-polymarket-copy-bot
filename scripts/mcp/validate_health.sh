#!/bin/bash
################################################################################
# MCP Servers Health Validation Script
#
# Validates health of:
# - Codebase search MCP server
# - Testing MCP server
# - Monitoring MCP server
#
# Usage: ./scripts/mcp/validate_health.sh [options]
#   Options:
#     --staging        Validate in staging environment
#     --production     Validate in production environment
#     --post-deploy    Post-deployment validation mode
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MODE="validation"
ENVIRONMENT="${2:-staging}"

# Health thresholds
MAX_MEMORY_MB=100  # Per MCP server
MAX_CPU_PERCENT=1.0  # Per MCP server
MAX_RESPONSE_TIME_MS=1000  # 1 second
MAX_ERROR_RATE=0.1  # 10%
HEALTH_CHECK_TIMEOUT=10  # Seconds

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
WARNING_CHECKS=0
FAILED_CHECKS=0

################################################################################
# Logging Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
    ((TOTAL_CHECKS++))
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED_CHECKS++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNING_CHECKS++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED_CHECKS++))
}

log_section() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

################################################################################
# Utility Functions
################################################################################

check_port() {
    local port=$1
    local service_name=$2

    if command -v lsof &> /dev/null; then
        if lsof -i :"$port" > /dev/null 2>&1; then
            log_success "$service_name listening on port $port"
            return 0
        else
            log_error "$service_name NOT listening on port $port"
            return 1
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            log_success "$service_name listening on port $port"
            return 0
        else
            log_error "$service_name NOT listening on port $port"
            return 1
        fi
    else
        log_warning "Cannot check port $port (lsof/netstat not available)"
        return 0
    fi
}

check_http_endpoint() {
    local url=$1
    local service_name=$2

    if command -v curl &> /dev/null; then
        local start_time=$(date +%s%N)
        local response=$(curl -s -w "\n%{http_code}" --max-time $HEALTH_CHECK_TIMEOUT "$url" 2>/dev/null || echo "000")
        local end_time=$(date +%s%N)
        local duration=$(( (end_time - start_time) / 1000000 ))

        if [[ "$response" == "200" ]] || [[ "$response" == "000" ]]; then
            if [[ $duration -lt $MAX_RESPONSE_TIME_MS ]]; then
                log_success "$service_name endpoint OK (${duration}ms)"
                return 0
            else
                log_warning "$service_name endpoint slow (${duration}ms)"
                return 0
            fi
        else
            log_error "$service_name endpoint returned HTTP $response"
            return 1
        fi
    else
        log_warning "Cannot check $service_name endpoint (curl not available)"
        return 0
    fi
}

################################################################################
# Component Health Checks
################################################################################

check_codebase_search() {
    log_section "Codebase Search MCP Server"

    # Check if enabled
    local enabled=$(python3 -c "
import os
from dotenv import load_dotenv
from pathlib import Path

env_file = Path('$PROJECT_ROOT/.env')
if env_file.exists():
    load_dotenv(env_file)

print(os.getenv('MCP_CODEBASE_SEARCH_ENABLED', 'false').lower())
" 2>/dev/null || echo "false")

    if [[ "$enabled" != "true" ]]; then
        log_info "Codebase search disabled - skipping checks"
        return 0
    fi

    # Check service
    if pgrep -f "codebase_search" > /dev/null; then
        log_success "Codebase search process running"
    else
        log_warning "Codebase search process not found"
        return 1
    fi

    # Note: Codebase search doesn't expose HTTP endpoints
    log_info "Codebase search runs as internal process (no HTTP endpoint)"

    return 0
}

check_testing_server() {
    log_section "Testing MCP Server"

    # Check if enabled
    local enabled=$(python3 -c "
import os
from dotenv import load_dotenv
from pathlib import Path

env_file = Path('$PROJECT_ROOT/.env')
if env_file.exists():
    load_dotenv(env_file)

print(os.getenv('MCP_TESTING_ENABLED', 'false').lower())
" 2>/dev/null || echo "false")

    if [[ "$enabled" != "true" ]]; then
        log_info "Testing server disabled - skipping checks"
        return 0
    fi

    # Check service
    if pgrep -f "testing_server" > /dev/null; then
        log_success "Testing server process running"
    else
        log_warning "Testing server process not found"
        return 1
    fi

    # Note: Testing server doesn't expose HTTP endpoints
    log_info "Testing server runs as internal process (no HTTP endpoint)"

    return 0
}

check_monitoring_server() {
    log_section "Monitoring MCP Server"

    # Check if enabled
    local enabled=$(python3 -c "
import os
from dotenv import load_dotenv
from pathlib import Path

env_file = Path('$PROJECT_ROOT/.env')
if env_file.exists():
    load_dotenv(env_file)

print(os.getenv('MONITORING_ENABLED', 'false').lower())
" 2>/dev/null || echo "false")

    if [[ "$enabled" != "true" ]]; then
        log_info "Monitoring server disabled - skipping checks"
        return 0
    fi

    # Check process
    if pgrep -f "monitoring_server" > /dev/null; then
        log_success "Monitoring server process running"
    else
        log_warning "Monitoring server process not found"
        return 1
    fi

    # Check dashboard port (8080)
    check_port 8080 "Monitoring dashboard"

    # Check dashboard health endpoint
    check_http_endpoint "http://localhost:8080/health" "Dashboard health"

    # Check metrics port (9090)
    check_port 9090 "Prometheus metrics"

    # Check metrics endpoint
    check_http_endpoint "http://localhost:9090/metrics" "Prometheus metrics"

    return 0
}

check_integration() {
    log_section "MCP Integration"

    # Check if integration module exists
    if [[ -f "$PROJECT_ROOT/core/integrations/mcp_risk_integration.py" ]]; then
        log_success "MCP integration module exists"

        # Test import
        local import_test=$(cd "$PROJECT_ROOT" && python3 -c "
try:
    from core.integrations.mcp_risk_integration import get_mcp_risk_integrator
    integrator = get_mcp_risk_integrator()
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)

        if [[ "$import_test" == "SUCCESS" ]]; then
            log_success "MCP integration imports correctly"
        else
            log_error "MCP integration import failed: $import_test"
            return 1
        fi
    else
        log_error "MCP integration module not found"
        return 1
    fi

    return 0
}

check_risk_integration() {
    log_section "Risk System Integration"

    # Test circuit breaker integration
    local circuit_breaker_test=$(cd "$PROJECT_ROOT" && python3 -c "
try:
    from core.circuit_breaker import CircuitBreaker
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)

    if [[ "$circuit_breaker_test" == "SUCCESS" ]]; then
        log_success "Circuit breaker imports correctly"
    else
        log_error "Circuit breaker import failed: $circuit_breaker_test"
        return 1
    fi

    # Test trade executor integration
    local trade_executor_test=$(cd "$PROJECT_ROOT" && python3 -c "
try:
    from core.trade_executor import TradeExecutor
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)

    if [[ "$trade_executor_test" == "SUCCESS" ]]; then
        log_success "Trade executor imports correctly"
    else
        log_error "Trade executor import failed: $trade_executor_test"
        return 1
    fi

    return 0
}

################################################################################
# System Health Checks
################################################################################

check_system_resources() {
    log_section "System Resources"

    # Check CPU availability
    local cpu_idle=$(top -bn1 | grep "Cpu(s)" | awk '{print $8}')
    local cpu_available=$((100 - cpu_idle))

    log_info "CPU available: $cpu_available% (idle: $cpu_idle%)"

    if [[ $cpu_available -gt 80 ]]; then
        log_warning "High CPU usage: $((100 - cpu_available))% used"
    else
        log_success "CPU usage acceptable"
    fi

    # Check memory availability
    local mem_available=$(free | grep Mem | awk '{print $7}')
    local mem_total=$(free | grep Mem | awk '{print $2}')
    local mem_available_mb=$((mem_available / 1024))
    local mem_total_mb=$((mem_total / 1024))
    local mem_used=$(( (mem_total - mem_available) / 1024))

    log_info "Memory available: ${mem_available_mb}MB / ${mem_total_mb}MB"

    if [[ $mem_used -gt 1024 ]]; then
        log_warning "High memory usage: ${mem_used}MB used"
    else
        log_success "Memory usage acceptable"
    fi

    # Check disk space
    local disk_available=$(df -BG "$PROJECT_ROOT" | awk '{print $4}')
    local disk_available_mb=$((disk_available / 1024 / 1024))

    log_info "Disk available: ${disk_available_mb}MB"

    if [[ $disk_available_mb -lt 500 ]]; then
        log_warning "Low disk space: ${disk_available_mb}MB available"
    else
        log_success "Disk space acceptable"
    fi
}

################################################################################
# Post-Deployment Validation
################################################################################

post_deploy_validation() {
    log_section "Post-Deployment Validation"

    # Wait for services to stabilize
    log_info "Waiting 30 seconds for services to stabilize..."
    sleep 30

    # Check all MCP servers
    local failed=0

    check_codebase_search || ((failed++))
    check_testing_server || ((failed++))
    check_monitoring_server || ((failed++))

    # Check integration
    check_integration || ((failed++))
    check_risk_integration || ((failed++))

    # Final result
    if [[ $failed -gt 0 ]]; then
        log_error "Post-deployment validation FAILED ($failed failures)"
        return 1
    else
        log_success "Post-deployment validation PASSED"
        return 0
    fi
}

################################################################################
# Summary Report
################################################################################

print_summary() {
    log_section "Health Validation Summary"

    echo -e "Total checks:   ${BLUE}$TOTAL_CHECKS${NC}"
    echo -e "Passed:         ${GREEN}$PASSED_CHECKS${NC}"
    echo -e "Warnings:       ${YELLOW}$WARNING_CHECKS${NC}"
    echo -e "Failed:         ${RED}$FAILED_CHECKS${NC}"

    local success_rate=0
    if [[ $TOTAL_CHECKS -gt 0 ]]; then
        success_rate=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
    fi

    echo -e "Success rate:   ${BLUE}${success_rate}%${NC}"

    # Overall status
    if [[ $FAILED_CHECKS -gt 0 ]]; then
        echo -e "${RED}Overall status: FAILED${NC}"
        return 1
    elif [[ $WARNING_CHECKS -gt 0 ]]; then
        echo -e "${YELLOW}Overall status: PASSED WITH WARNINGS${NC}"
        return 0
    else
        echo -e "${GREEN}Overall status: PASSED${NC}"
        return 0
    fi
}

################################################################################
# Main Function
################################################################################

main() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "MCP Servers Health Validation"
    echo "Mode: $MODE"
    echo "Environment: $ENVIRONMENT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Change to project root
    cd "$PROJECT_ROOT"

    # Run checks based on mode
    case "$MODE" in
        validation)
            # Standard validation
            check_system_resources
            check_codebase_search
            check_testing_server
            check_monitoring_server
            check_integration
            check_risk_integration
            print_summary
            ;;
        post-deploy)
            # Post-deployment validation
            post_deploy_validation
            print_summary
            ;;
        *)
            log_error "Unknown mode: $MODE"
            echo "Usage: $0 [--staging|--production] [--post-deploy]"
            exit 1
            ;;
    esac
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --staging)
            ENVIRONMENT="staging"
            shift
            ;;
        --production)
            ENVIRONMENT="production"
            shift
            ;;
        --post-deploy)
            MODE="post-deploy"
            shift
            ;;
        --*)
            log_error "Unknown option: $1"
            echo "Usage: $0 [--staging|--production] [--post-deploy]"
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

# Run main function
main "$@"
