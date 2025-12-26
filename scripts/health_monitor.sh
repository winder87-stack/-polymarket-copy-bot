#!/bin/bash
# Comprehensive Health Monitoring for Polymarket Copy Bot
# Native monitoring without container dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-production}"
CHECK_TYPE="${2:-comprehensive}"
ALERT_THRESHOLD="${3:-warning}"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        SERVICE_NAME="polymarket-bot"
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        HEALTH_PORT=8000
        ;;
    staging)
        SERVICE_NAME="polymarket-bot-staging"
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        HEALTH_PORT=8001
        ;;
    development)
        SERVICE_NAME=""
        BOT_USER="${USER:-$(whoami)}"
        BOT_GROUP="${BOT_USER:-$(whoami)}"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        HEALTH_PORT=8002
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Health status tracking
HEALTH_STATUS="healthy"
ISSUES_FOUND=0
WARNINGS_FOUND=0

# Function to log health check results
log_health() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_file="$PROJECT_ROOT/logs/health_monitor_$ENVIRONMENT.log"

    echo "[$timestamp] [$level] $message" >> "$log_file"

    case "$level" in
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ((ISSUES_FOUND++))
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ((WARNINGS_FOUND++))
            ;;
        "INFO")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
    esac
}

# Function to check systemd service status
check_service_status() {
    log_health "INFO" "Checking systemd service status..."

    if [ -z "$SERVICE_NAME" ]; then
        log_health "INFO" "Development environment - skipping service check"
        return 0
    fi

    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        log_health "ERROR" "Service $SERVICE_NAME is not running"

        # Get service status details
        local status=$(systemctl status "$SERVICE_NAME" 2>/dev/null | grep -E "(Active|Loaded|Main PID)" | head -3)
        log_health "INFO" "Service status: $status"

        return 1
    fi

    # Check if service is enabled
    if ! systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        log_health "WARNING" "Service $SERVICE_NAME is not enabled to start on boot"
    fi

    log_health "SUCCESS" "Service $SERVICE_NAME is running"
}

# Function to check process health
check_process_health() {
    log_health "INFO" "Checking process health..."

    # Find bot processes
    local bot_pids=$(pgrep -f "python.*main.py" || true)

    if [ -z "$bot_pids" ]; then
        log_health "ERROR" "No bot processes found running"
        return 1
    fi

    log_health "SUCCESS" "Found $(echo "$bot_pids" | wc -l) bot process(es)"

    # Check process age and CPU/memory usage
    for pid in $bot_pids; do
        if [ -d "/proc/$pid" ]; then
            local cpu_usage=$(ps -p "$pid" -o %cpu= | tr -d ' ')
            local mem_usage=$(ps -p "$pid" -o %mem= | tr -d ' ')
            local process_age=$(ps -p "$pid" -o etimes= | tr -d ' ')

            log_health "INFO" "PID $pid: CPU=${cpu_usage}%, MEM=${mem_usage}%, AGE=${process_age}s"

            # Alert thresholds
            if (( $(echo "$cpu_usage > 80" | bc -l 2>/dev/null || echo "0") )); then
                log_health "WARNING" "High CPU usage on PID $pid: ${cpu_usage}%"
            fi

            if (( $(echo "$mem_usage > 80" | bc -l 2>/dev/null || echo "0") )); then
                log_health "WARNING" "High memory usage on PID $pid: ${mem_usage}%"
            fi
        else
            log_health "WARNING" "Process $pid not found in /proc"
        fi
    done
}

# Function to check resource usage
check_resource_usage() {
    log_health "INFO" "Checking system resource usage..."

    # CPU usage
    local cpu_usage=$(uptime | awk -F'load average:' '{ print $2 }' | awk '{ print $1 }' | sed 's/,//' || echo "unknown")
    log_health "INFO" "System load average: $cpu_usage"

    # Memory usage
    local mem_info=$(free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2 }')
    log_health "INFO" "Memory usage: $mem_info"

    if (( $(echo "$mem_info > 90" | bc -l 2>/dev/null || echo "0") )); then
        log_health "ERROR" "Critical memory usage: $mem_info"
        HEALTH_STATUS="critical"
    elif (( $(echo "$mem_info > 80" | bc -l 2>/dev/null || echo "0") )); then
        log_health "WARNING" "High memory usage: $mem_info"
        if [ "$HEALTH_STATUS" = "healthy" ]; then
            HEALTH_STATUS="degraded"
        fi
    fi

    # Disk usage for project directory
    local disk_usage=$(df "$PROJECT_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
    log_health "INFO" "Disk usage: $disk_usage%"

    if [ "$disk_usage" -gt 95 ]; then
        log_health "ERROR" "Critical disk usage: $disk_usage%"
        HEALTH_STATUS="critical"
    elif [ "$disk_usage" -gt 85 ]; then
        log_health "WARNING" "High disk usage: $disk_usage%"
        if [ "$HEALTH_STATUS" = "healthy" ]; then
            HEALTH_STATUS="degraded"
        fi
    fi

    # Check available disk space
    local available_space=$(df -BG "$PROJECT_DIR" | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "${available_space:-0}" -lt 1 ]; then
        log_health "ERROR" "Less than 1GB disk space available"
        HEALTH_STATUS="critical"
    fi
}

# Function to check network connectivity
check_network_connectivity() {
    log_health "INFO" "Checking network connectivity..."

    # Check basic internet connectivity
    if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
        log_health "ERROR" "No internet connectivity detected"
        return 1
    fi

    # Check RPC endpoint connectivity
    if [ -f "$PROJECT_DIR/.env" ]; then
        local rpc_url=$(grep "POLYGON_RPC_URL" "$PROJECT_DIR/.env" | cut -d'=' -f2 | tr -d '"' 2>/dev/null || echo "")

        if [ -n "$rpc_url" ]; then
            if ! curl -f --max-time 5 "$rpc_url" >/dev/null 2>&1; then
                log_health "WARNING" "Cannot connect to RPC endpoint: $rpc_url"
            else
                log_health "SUCCESS" "RPC endpoint reachable"
            fi
        fi
    fi

    # Check if health endpoint is available
    if curl -f --max-time 3 "http://localhost:$HEALTH_PORT/health" >/dev/null 2>&1; then
        log_health "SUCCESS" "Health endpoint responding on port $HEALTH_PORT"
    else
        log_health "WARNING" "Health endpoint not responding on port $HEALTH_PORT"
    fi
}

# Function to check blockchain sync status
check_blockchain_sync() {
    log_health "INFO" "Checking blockchain sync status..."

    # This would integrate with your bot's blockchain monitoring
    # For now, check if the bot process is making RPC calls

    local rpc_calls=$(netstat -tpn 2>/dev/null | grep -c ":443 " || echo "0")
    if [ "$rpc_calls" -gt 0 ]; then
        log_health "SUCCESS" "Active network connections detected ($rpc_calls)"
    else
        log_health "WARNING" "No active network connections detected"
    fi

    # Check for recent log activity
    local recent_logs=$(find "$PROJECT_ROOT/logs" -name "*.log" -mmin -5 2>/dev/null | wc -l)
    if [ "$recent_logs" -gt 0 ]; then
        log_health "SUCCESS" "Recent log activity detected"
    else
        log_health "WARNING" "No recent log activity (last 5 minutes)"
    fi
}

# Function to check log files
check_log_files() {
    log_health "INFO" "Checking log files..."

    local log_dir="$PROJECT_ROOT/logs"

    if [ ! -d "$log_dir" ]; then
        log_health "ERROR" "Log directory not found: $log_dir"
        return 1
    fi

    # Check for error patterns in recent logs
    local error_count=$(find "$log_dir" -name "*.log" -exec grep -l "ERROR\|CRITICAL\|FATAL" {} \; 2>/dev/null | wc -l)
    if [ "$error_count" -gt 0 ]; then
        log_health "WARNING" "Found errors in $error_count log file(s)"

        # Show recent errors
        find "$log_dir" -name "*.log" -exec tail -20 {} \; | grep -E "ERROR|CRITICAL|FATAL" | head -5 | while read -r line; do
            log_health "WARNING" "Recent error: $line"
        done
    fi

    # Check log file sizes
    local large_logs=$(find "$log_dir" -name "*.log" -size +100M 2>/dev/null | wc -l)
    if [ "$large_logs" -gt 0 ]; then
        log_health "WARNING" "Found $large_logs log file(s) larger than 100MB"
    fi

    # Check log rotation
    local old_logs=$(find "$log_dir" -name "*.log.*" -mtime +7 2>/dev/null | wc -l)
    if [ "$old_logs" -gt 0 ]; then
        log_health "INFO" "Found $old_logs old rotated log files"
    fi

    log_health "SUCCESS" "Log file check completed"
}

# Function to check data integrity
check_data_integrity() {
    log_health "INFO" "Checking data integrity..."

    local data_dir="$PROJECT_ROOT/data"

    if [ ! -d "$data_dir" ]; then
        log_health "WARNING" "Data directory not found: $data_dir"
        return 0
    fi

    # Check trade history files
    local trade_files=$(find "$data_dir/trade_history" -name "*.json" 2>/dev/null | wc -l)
    log_health "INFO" "Found $trade_files trade history files"

    # Validate JSON files
    local invalid_json=0
    find "$data_dir/trade_history" -name "*.json" -exec python3 -m json.tool {} \; >/dev/null 2>&1 || ((invalid_json++)) &
    wait

    if [ "$invalid_json" -gt 0 ]; then
        log_health "WARNING" "Found $invalid_json invalid JSON files"
    fi

    # Check for backup files
    local backup_files=$(find "$PROJECT_ROOT/backups" -name "*.tar.gz" 2>/dev/null | wc -l)
    log_health "INFO" "Found $backup_files backup files"

    log_health "SUCCESS" "Data integrity check completed"
}

# Function to check security status
check_security_status() {
    log_health "INFO" "Checking security status..."

    # Check file permissions
    local world_writable=$(find "$PROJECT_DIR" -type f -perm -002 2>/dev/null | wc -l)
    if [ "$world_writable" -gt 0 ]; then
        log_health "ERROR" "Found $world_writable world-writable files"
        HEALTH_STATUS="critical"
    fi

    # Check for unauthorized SUID files
    local suid_files=$(find "$PROJECT_DIR" -type f -perm -4000 2>/dev/null | wc -l)
    if [ "$suid_files" -gt 0 ]; then
        log_health "WARNING" "Found $suid_files SUID files"
    fi

    # Check if security monitoring is running
    if ! pgrep -f "security_monitor.sh" >/dev/null 2>&1; then
        log_health "WARNING" "Security monitoring not running"
    fi

    log_health "SUCCESS" "Security status check completed"
}

# Function to check configuration validity
check_configuration() {
    log_health "INFO" "Checking configuration validity..."

    # Check if .env file exists and is readable
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        log_health "ERROR" "Environment file not found: $PROJECT_DIR/.env"
        return 1
    fi

    # Check critical configuration variables
    local required_vars=("PRIVATE_KEY" "POLYGON_RPC_URL")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" "$PROJECT_DIR/.env"; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_health "ERROR" "Missing required configuration variables: ${missing_vars[*]}"
        return 1
    fi

    # Check wallets configuration
    if [ ! -f "$PROJECT_DIR/config/wallets.json" ]; then
        log_health "ERROR" "Wallets configuration not found"
        return 1
    fi

    # Validate JSON syntax
    if ! python3 -m json.tool "$PROJECT_DIR/config/wallets.json" >/dev/null 2>&1; then
        log_health "ERROR" "Invalid JSON in wallets configuration"
        return 1
    fi

    log_health "SUCCESS" "Configuration validation passed"
}

# Function to generate health report
generate_health_report() {
    local report_file="$PROJECT_ROOT/logs/health_report_$ENVIRONMENT.json"
    local timestamp=$(date -Iseconds)

    cat > "$report_file" << EOF
{
  "timestamp": "$timestamp",
  "environment": "$ENVIRONMENT",
  "overall_status": "$HEALTH_STATUS",
  "issues_found": $ISSUES_FOUND,
  "warnings_found": $WARNINGS_FOUND,
  "checks_performed": [
    "service_status",
    "process_health",
    "resource_usage",
    "network_connectivity",
    "blockchain_sync",
    "log_files",
    "data_integrity",
    "security_status",
    "configuration"
  ],
  "recommendations": [
EOF

    # Add recommendations based on findings
    if [ $ISSUES_FOUND -gt 0 ]; then
        cat >> "$report_file" << EOF
    "Immediate attention required - check logs for details",
EOF
    fi

    if [ "$HEALTH_STATUS" = "critical" ]; then
        cat >> "$report_file" << EOF
    "Critical issues detected - consider service restart",
EOF
    fi

    if [ $WARNINGS_FOUND -gt 0 ]; then
        cat >> "$report_file" << EOF
    "Review warnings in log files",
EOF
    fi

    cat >> "$report_file" << EOF
    "Regular health monitoring recommended"
  ]
}
EOF

    log_health "SUCCESS" "Health report generated: $report_file"
}

# Function to send alerts
send_alerts() {
    if [ "$ISSUES_FOUND" -eq 0 ] && [ "$WARNINGS_FOUND" -eq 0 ]; then
        return 0
    fi

    log_health "INFO" "Sending alerts for health issues..."

    # This would integrate with your alerting system (email, Slack, etc.)
    # For now, just log the alerts

    if [ "$ISSUES_FOUND" -gt 0 ]; then
        log_health "ERROR" "ALERT: $ISSUES_FOUND critical issues detected in $ENVIRONMENT environment"
    fi

    if [ "$WARNINGS_FOUND" -gt 0 ]; then
        log_health "WARNING" "ALERT: $WARNINGS_FOUND warnings detected in $ENVIRONMENT environment"
    fi

    # Could send email alerts here
    # echo "Health check failed" | mail -s "Polymarket Bot Health Alert" admin@example.com
}

# Main execution
main() {
    log_health "INFO" "Starting comprehensive health check for $ENVIRONMENT environment"

    # Run all checks based on type
    case "$CHECK_TYPE" in
        quick)
            check_service_status
            check_process_health
            check_resource_usage
            ;;
        comprehensive|*)
            check_service_status
            check_process_health
            check_resource_usage
            check_network_connectivity
            check_blockchain_sync
            check_log_files
            check_data_integrity
            check_security_status
            check_configuration
            ;;
    esac

    # Determine overall health status
    if [ $ISSUES_FOUND -gt 0 ]; then
        HEALTH_STATUS="unhealthy"
    elif [ $WARNINGS_FOUND -gt 0 ]; then
        HEALTH_STATUS="degraded"
    else
        HEALTH_STATUS="healthy"
    fi

    # Generate report
    generate_health_report

    # Send alerts if needed
    send_alerts

    # Output final status
    echo ""
    case "$HEALTH_STATUS" in
        "healthy")
            echo -e "${GREEN}🎉 Health Status: HEALTHY ($WARNINGS_FOUND warnings, $ISSUES_FOUND issues)${NC}"
            ;;
        "degraded")
            echo -e "${YELLOW}⚠️  Health Status: DEGRADED ($WARNINGS_FOUND warnings, $ISSUES_FOUND issues)${NC}"
            ;;
        "unhealthy")
            echo -e "${RED}❌ Health Status: UNHEALTHY ($WARNINGS_FOUND warnings, $ISSUES_FOUND issues)${NC}"
            exit 1
            ;;
        "critical")
            echo -e "${RED}🚨 Health Status: CRITICAL ($WARNINGS_FOUND warnings, $ISSUES_FOUND issues)${NC}"
            exit 1
            ;;
    esac

    log_health "INFO" "Health check completed - Status: $HEALTH_STATUS"
}

# Parse command line arguments
case "${1:-help}" in
    production|staging|development)
        main "$@"
        ;;
    help|*)
        echo -e "${BLUE}Comprehensive Health Monitor for Polymarket Copy Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <environment> [check_type] [alert_threshold]"
        echo ""
        echo -e "${YELLOW}Environments:${NC}"
        echo "  production  - Production environment"
        echo "  staging     - Staging environment"
        echo "  development - Development environment"
        echo ""
        echo -e "${YELLOW}Check Types:${NC}"
        echo "  quick         - Basic service and resource checks"
        echo "  comprehensive - Full health assessment (default)"
        echo ""
        echo -e "${YELLOW}Alert Thresholds:${NC}"
        echo "  warning  - Alert on warnings and errors (default)"
        echo "  error    - Alert only on errors"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  $0 production comprehensive warning"
        echo "  $0 staging quick"
        echo "  $0 development"
        echo ""
        echo -e "${YELLOW}Exit Codes:${NC}"
        echo "  0 - Healthy or degraded (warnings only)"
        echo "  1 - Unhealthy or critical issues found"
        exit 0
        ;;
esac
