#!/bin/bash
# Staging Environment Monitoring Script
# ===========================================
#
# This script monitors the staging environment and provides
# real-time status updates during the 7-day testing period.
#
# Usage: ./scripts/monitor_staging.sh [command]
#
# Commands:
#   status     - Show current staging status
#   logs       - Tail staging logs
#   health     - Run health check
#   trades     - Show recent trades
#   alerts     - Show recent alerts
#   stop       - Stop staging environment
#   start      - Start staging environment
#   restart    - Restart staging environment
#
# ===========================================

set -e

PROJECT_DIR="/home/polymarket-staging/polymarket-copy-bot"
SERVICE_NAME="polymarket-bot-staging"
LOG_FILE="$PROJECT_DIR/logs/polymarket_bot_staging.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Helper functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_info_blue() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Check if running as root for service operations
check_root() {
    if [ "$(id -u)" != "0" ] && [[ "$1" =~ ^(start|stop|restart)$ ]]; then
        log_error "Service operations require root privileges. Use sudo."
        exit 1
    fi
}

# Show staging status
show_status() {
    echo "🚨 STAGING ENVIRONMENT STATUS 🚨"
    echo "================================="

    # Service status
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        log_info "Service: RUNNING"
        echo "  PID: $(systemctl show "$SERVICE_NAME" -p MainPID --value)"
        echo "  Uptime: $(systemctl show "$SERVICE_NAME" -p ActiveEnterTimestamp --value)"
    else
        log_error "Service: STOPPED"
        echo "  Status: $(systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo 'unknown')"
    fi

    echo ""

    # Configuration check
    if [ -f "$PROJECT_DIR/.env.staging" ]; then
        log_info "Configuration: PRESENT"
    else
        log_warn "Configuration: MISSING (.env.staging not found)"
    fi

    # Log file check
    if [ -f "$LOG_FILE" ]; then
        log_info "Log file: PRESENT ($(stat -c%s "$LOG_FILE" 2>/dev/null || echo "size unknown") bytes)"
        echo "  Last modified: $(stat -c%y "$LOG_FILE" 2>/dev/null || echo "unknown")"
    else
        log_warn "Log file: MISSING"
    fi

    echo ""

    # Recent log entries
    if [ -f "$LOG_FILE" ]; then
        echo "📋 Recent Log Entries:"
        echo "----------------------"
        tail -10 "$LOG_FILE" 2>/dev/null || echo "No log entries found"
        echo ""
    fi

    # Trade statistics
    if [ -f "$LOG_FILE" ]; then
        echo "📊 Staging Statistics:"
        echo "----------------------"
        echo "  Total trades executed: $(grep -c "Staging trade.*executed successfully" "$LOG_FILE" 2>/dev/null || echo "0")"
        echo "  Failed trades: $(grep -c "Staging trade failed" "$LOG_FILE" 2>/dev/null || echo "0")"
        echo "  Alerts sent: $(grep -c "Staging Alert:" "$LOG_FILE" 2>/dev/null || echo "0")"
        echo "  Health checks: $(grep -c "Staging health check" "$LOG_FILE" 2>/dev/null || echo "0")"
        echo ""
    fi
}

# Show recent trades
show_trades() {
    echo "📈 RECENT STAGING TRADES"
    echo "========================="

    if [ -f "$LOG_FILE" ]; then
        echo "Recent trades (last 24 hours):"
        echo "-------------------------------"
        grep -E "(Staging trade.*executed|TRADE_EXECUTED)" "$LOG_FILE" |
            grep "$(date -d 'yesterday' +%Y-%m-%d)" || echo "No trades in last 24 hours"

        echo ""
        echo "Trade summary:"
        echo "--------------"
        echo "  Today: $(grep -c "Staging trade.*executed successfully" "$LOG_FILE" |
                  xargs -I {} sh -c 'grep "$(date +%Y-%m-%d)" <<< "{}"' || echo "0")"
        echo "  This week: $(grep -c "Staging trade.*executed successfully" "$LOG_FILE")"
    else
        log_error "Log file not found"
    fi
}

# Show alerts
show_alerts() {
    echo "🚨 STAGING ALERTS"
    echo "=================="

    if [ -f "$LOG_FILE" ]; then
        echo "Recent alerts (last 50):"
        echo "------------------------"
        grep "Staging Alert:" "$LOG_FILE" | tail -20 || echo "No recent alerts"
        echo ""
        echo "Alert summary:"
        echo "--------------"
        echo "  Total alerts: $(grep -c "Staging Alert:" "$LOG_FILE" 2>/dev/null || echo "0")"
        echo "  Error alerts: $(grep -c "Staging Alert.*ERROR" "$LOG_FILE" 2>/dev/null || echo "0")"
        echo "  Trade alerts: $(grep -c "Staging Alert.*TRADE" "$LOG_FILE" 2>/dev/null || echo "0")"
    else
        log_error "Log file not found"
    fi
}

# Run health check
run_health_check() {
    echo "🏥 STAGING HEALTH CHECK"
    echo "======================="

    # Service health
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        log_info "Service Status: HEALTHY"
    else
        log_error "Service Status: UNHEALTHY"
    fi

    # Process health
    PID=$(systemctl show "$SERVICE_NAME" -p MainPID --value 2>/dev/null)
    if [ -n "$PID" ] && [ "$PID" != "0" ]; then
        if ps -p "$PID" > /dev/null 2>&1; then
            MEM_USAGE=$(ps -o pmem= -p "$PID" | tr -d ' ')
            CPU_USAGE=$(ps -o pcpu= -p "$PID" | tr -d ' ')
            log_info "Process Status: HEALTHY (PID: $PID, MEM: ${MEM_USAGE}%, CPU: ${CPU_USAGE}%)"
        else
            log_error "Process Status: UNHEALTHY (PID $PID not found)"
        fi
    else
        log_error "Process Status: NO PID FOUND"
    fi

    # Disk space
    DISK_USAGE=$(df /home | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -gt 90 ]; then
        log_error "Disk Usage: CRITICAL (${DISK_USAGE}%)"
    elif [ "$DISK_USAGE" -gt 80 ]; then
        log_warn "Disk Usage: WARNING (${DISK_USAGE}%)"
    else
        log_info "Disk Usage: HEALTHY (${DISK_USAGE}%)"
    fi

    # Log file size
    if [ -f "$LOG_FILE" ]; then
        LOG_SIZE=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo "0")
        LOG_SIZE_MB=$((LOG_SIZE / 1024 / 1024))
        if [ "$LOG_SIZE_MB" -gt 100 ]; then
            log_warn "Log Size: LARGE (${LOG_SIZE_MB}MB)"
        else
            log_info "Log Size: HEALTHY (${LOG_SIZE_MB}MB)"
        fi
    fi

    # Recent errors
    if [ -f "$LOG_FILE" ]; then
        ERROR_COUNT=$(grep -c -E "(ERROR|CRITICAL)" "$LOG_FILE" 2>/dev/null || echo "0")
        if [ "$ERROR_COUNT" -gt 0 ]; then
            log_warn "Recent Errors: $ERROR_COUNT found"
            echo "  Last error: $(grep -E "(ERROR|CRITICAL)" "$LOG_FILE" | tail -1 | cut -d' ' -f6-)"
        else
            log_info "Recent Errors: NONE"
        fi
    fi
}

# Main command processing
COMMAND=${1:-status}

check_root "$COMMAND"

case "$COMMAND" in
    status)
        show_status
        ;;
    logs)
        echo "📋 Tailing staging logs (Ctrl+C to stop):"
        echo "=========================================="
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            log_error "Log file not found: $LOG_FILE"
        fi
        ;;
    health)
        run_health_check
        ;;
    trades)
        show_trades
        ;;
    alerts)
        show_alerts
        ;;
    start)
        echo "▶️ Starting staging service..."
        systemctl start "$SERVICE_NAME"
        sleep 2
        systemctl status "$SERVICE_NAME" --no-pager
        ;;
    stop)
        echo "⏹️ Stopping staging service..."
        systemctl stop "$SERVICE_NAME"
        sleep 2
        systemctl status "$SERVICE_NAME" --no-pager
        ;;
    restart)
        echo "🔄 Restarting staging service..."
        systemctl restart "$SERVICE_NAME"
        sleep 2
        systemctl status "$SERVICE_NAME" --no-pager
        ;;
    *)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  status     - Show current staging status"
        echo "  logs       - Tail staging logs"
        echo "  health     - Run health check"
        echo "  trades     - Show recent trades"
        echo "  alerts     - Show recent alerts"
        echo "  start      - Start staging environment"
        echo "  stop       - Stop staging environment"
        echo "  restart    - Restart staging environment"
        echo ""
        echo "🚨 STAGING ENVIRONMENT - TESTNET ONLY 🚨"
        exit 1
        ;;
esac

echo ""
echo "🚨 STAGING ENVIRONMENT - TESTNET ONLY 🚨"
