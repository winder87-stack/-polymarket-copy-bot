#!/bin/bash
# Automated Maintenance Tasks for Polymarket Copy Bot
# Daily maintenance operations for system health

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
MAINTENANCE_TYPE="${1:-daily}"
ENVIRONMENT="${2:-production}"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        ;;
    staging)
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        ;;
    development)
        BOT_USER="${USER:-$(whoami)}"
        BOT_GROUP="${BOT_USER:-$(whoami)}"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Maintenance tracking
MAINTENANCE_LOG="$PROJECT_ROOT/logs/automated_maintenance_$ENVIRONMENT.log"
MAINTENANCE_SUCCESS=0
MAINTENANCE_WARNINGS=0
MAINTENANCE_ERRORS=0

# Function to log maintenance operations
log_maintenance() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] $message" >> "$MAINTENANCE_LOG"
    echo "[$timestamp] [$level] $message"

    case "$level" in
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ((MAINTENANCE_ERRORS++))
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ((MAINTENANCE_WARNINGS++))
            ;;
        "INFO")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ((MAINTENANCE_SUCCESS++))
            ;;
    esac
}

# Function to perform log rotation and cleanup
log_rotation_and_cleanup() {
    log_maintenance "INFO" "Starting log rotation and cleanup..."

    local log_dir="$PROJECT_ROOT/logs"
    local backup_dir="$PROJECT_ROOT/backups/logs"

    mkdir -p "$backup_dir"

    # Compress old log files
    find "$log_dir" -name "*.log" -mtime +1 -exec gzip {} \; 2>/dev/null || true

    # Move compressed logs to backup
    find "$log_dir" -name "*.log.gz" -mtime +7 -exec mv {} "$backup_dir/" \; 2>/dev/null || true

    # Remove very old archived logs (older than 30 days)
    find "$backup_dir" -name "*.log.gz" -mtime +30 -delete 2>/dev/null || true

    # Clean temporary files
    find "$PROJECT_ROOT/temp" -type f -mtime +1 -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -name "*.tmp" -mtime +1 -delete 2>/dev/null || true

    # Clean Python cache files
    find "$PROJECT_ROOT" -name "__pycache__" -type d -exec rm -rf {} \; 2>/dev/null || true
    find "$PROJECT_ROOT" -name "*.pyc" -delete 2>/dev/null || true

    # Clean old core dumps
    find "$PROJECT_ROOT" -name "core.*" -mtime +7 -delete 2>/dev/null || true

    log_maintenance "SUCCESS" "Log rotation and cleanup completed"
}

# Function to update dependencies securely
dependency_security_updates() {
    log_maintenance "INFO" "Checking for dependency security updates..."

    local requirements_file="$PROJECT_ROOT/requirements.txt"

    if [ ! -f "$requirements_file" ]; then
        log_maintenance "ERROR" "Requirements file not found: $requirements_file"
        return 1
    fi

    # Check if safety is available
    if ! command -v safety >/dev/null 2>&1; then
        log_maintenance "WARNING" "Safety tool not installed, installing..."
        if [ "$ENVIRONMENT" = "development" ]; then
            pip install safety
        else
            sudo -u "$BOT_USER" "$PROJECT_DIR/venv/bin/pip" install safety
        fi
    fi

    # Run safety check
    local safety_output
    if safety check --file "$requirements_file" --json > /tmp/safety_check.json 2>/dev/null; then
        local vuln_count=$(jq '.issues | length' /tmp/safety_check.json 2>/dev/null || echo "0")
        if [ "$vuln_count" -gt 0 ]; then
            log_maintenance "WARNING" "Found $vuln_count security vulnerabilities"

            # Update vulnerable packages
            jq -r '.issues[].package' /tmp/safety_check.json | sort | uniq | while read -r package; do
                log_maintenance "INFO" "Attempting to update vulnerable package: $package"

                if [ "$ENVIRONMENT" = "development" ]; then
                    pip install --upgrade "$package" 2>/dev/null || log_maintenance "WARNING" "Failed to update $package"
                else
                    sudo -u "$BOT_USER" "$PROJECT_DIR/venv/bin/pip" install --upgrade "$package" 2>/dev/null || log_maintenance "WARNING" "Failed to update $package"
                fi
            done

            # Re-run safety check
            if safety check --file "$requirements_file" --json >/dev/null 2>&1; then
                log_maintenance "SUCCESS" "Security updates applied"
            else
                log_maintenance "WARNING" "Some security issues remain"
            fi
        else
            log_maintenance "SUCCESS" "No security vulnerabilities found"
        fi
    else
        log_maintenance "WARNING" "Safety check failed - manual review recommended"
    fi

    # Clean up
    rm -f /tmp/safety_check.json
}

# Function to optimize database/filesystem
database_and_filesystem_optimization() {
    log_maintenance "INFO" "Performing database and filesystem optimization..."

    # Clean up old trade history files (keep last 90 days)
    local trade_history_dir="$PROJECT_ROOT/data/trade_history"
    if [ -d "$trade_history_dir" ]; then
        find "$trade_history_dir" -name "*.json" -mtime +90 -delete 2>/dev/null || true
        local cleaned_files=$(find "$trade_history_dir" -name "*.json" -mtime +90 2>/dev/null | wc -l)
        log_maintenance "INFO" "Cleaned up $cleaned_files old trade history files"
    fi

    # Defragment log files if needed
    local log_dir="$PROJECT_ROOT/logs"
    find "$log_dir" -name "*.log" -size +10M -exec logrotate -f /etc/logrotate.d/polymarket-$ENVIRONMENT \; 2>/dev/null || true

    # Optimize file permissions
    if [ "$ENVIRONMENT" != "development" ]; then
        find "$PROJECT_DIR" -type f -name "*.log" -exec chmod 640 {} \; 2>/dev/null || true
        find "$PROJECT_DIR" -type d -exec chmod 755 {} \; 2>/dev/null || true
    fi

    # Clean up broken symlinks
    find "$PROJECT_DIR" -type l -exec test ! -e {} \; -delete 2>/dev/null || true

    log_maintenance "SUCCESS" "Database and filesystem optimization completed"
}

# Function to check and renew certificates
certificate_renewal() {
    log_maintenance "INFO" "Checking certificate renewal status..."

    # This would check for SSL certificates if your bot uses them
    # For now, check if any certificate files exist and are nearing expiry

    local cert_files=$(find "$PROJECT_DIR" -name "*.pem" -o -name "*.crt" -o -name "*.key" 2>/dev/null)

    if [ -n "$cert_files" ]; then
        log_maintenance "INFO" "Found certificate files, checking expiry..."

        for cert_file in $cert_files; do
            if command -v openssl >/dev/null 2>&1; then
                local expiry_date=$(openssl x509 -in "$cert_file" -noout -enddate 2>/dev/null | cut -d= -f2 || echo "unknown")
                if [ "$expiry_date" != "unknown" ]; then
                    local days_until_expiry=$(( ($(date -d "$expiry_date" +%s) - $(date +%s)) / 86400 ))
                    if [ $days_until_expiry -lt 30 ]; then
                        log_maintenance "WARNING" "Certificate $cert_file expires in $days_until_expiry days"
                    else
                        log_maintenance "SUCCESS" "Certificate $cert_file valid for $days_until_expiry more days"
                    fi
                fi
            fi
        done
    else
        log_maintenance "INFO" "No certificate files found"
    fi

    log_maintenance "SUCCESS" "Certificate renewal check completed"
}

# Function to update system packages
system_package_updates() {
    log_maintenance "INFO" "Checking for system package updates..."

    if [ "$ENVIRONMENT" = "production" ]; then
        # Only check, don't auto-update in production
        local updates_available=$(apt list --upgradable 2>/dev/null | grep -v "Listing\|WARNING" | wc -l)

        if [ "$updates_available" -gt 0 ]; then
            log_maintenance "WARNING" "$updates_available system packages available for update"
            log_maintenance "INFO" "Manual system update recommended before bot updates"
        else
            log_maintenance "SUCCESS" "System packages are up to date"
        fi
    else
        log_maintenance "INFO" "Skipping system updates in $ENVIRONMENT environment"
    fi
}

# Function to backup critical data
maintenance_backup() {
    log_maintenance "INFO" "Creating maintenance backup..."

    # Create config backup
    "$SCRIPT_DIR/backup_secure.sh" "$ENVIRONMENT" config >/dev/null 2>&1 || log_maintenance "WARNING" "Config backup failed"

    # Create data backup (less frequent)
    if [ "$(date +%u)" = "7" ]; then  # Only on Sundays
        "$SCRIPT_DIR/backup_secure.sh" "$ENVIRONMENT" data >/dev/null 2>&1 || log_maintenance "WARNING" "Data backup failed"
    fi

    log_maintenance "SUCCESS" "Maintenance backup completed"
}

# Function to check system integrity
system_integrity_check() {
    log_maintenance "INFO" "Performing system integrity checks..."

    # Check filesystem integrity
    local fs_errors=$(dmesg | grep -i "filesystem error" | wc -l)
    if [ "$fs_errors" -gt 0 ]; then
        log_maintenance "ERROR" "Filesystem errors detected in system logs"
    fi

    # Check disk health (basic)
    local disk_health=$(df -h "$PROJECT_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_health" -gt 95 ]; then
        log_maintenance "ERROR" "Critical disk usage: ${disk_health}%"
    elif [ "$disk_health" -gt 85 ]; then
        log_maintenance "WARNING" "High disk usage: ${disk_health}%"
    fi

    # Check memory usage
    local mem_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    if [ "$mem_usage" -gt 90 ]; then
        log_maintenance "ERROR" "Critical memory usage: ${mem_usage}%"
    elif [ "$mem_usage" -gt 80 ]; then
        log_maintenance "WARNING" "High memory usage: ${mem_usage}%"
    fi

    log_maintenance "SUCCESS" "System integrity check completed"
}

# Function to generate maintenance report
generate_maintenance_report() {
    local report_file="$PROJECT_ROOT/logs/maintenance_report_$ENVIRONMENT.json"
    local timestamp=$(date -Iseconds)

    cat > "$report_file" << EOF
{
  "timestamp": "$timestamp",
  "environment": "$ENVIRONMENT",
  "maintenance_type": "$MAINTENANCE_TYPE",
  "results": {
    "successful_operations": $MAINTENANCE_SUCCESS,
    "warnings": $MAINTENANCE_WARNINGS,
    "errors": $MAINTENANCE_ERRORS
  },
  "operations_performed": [
    "log_rotation_and_cleanup",
    "dependency_security_updates",
    "database_and_filesystem_optimization",
    "certificate_renewal",
    "system_package_updates",
    "maintenance_backup",
    "system_integrity_check"
  ],
  "status": "$( [ $MAINTENANCE_ERRORS -eq 0 ] && echo "completed" || echo "completed_with_errors" )",
  "next_maintenance": "$(date -d "+1 day" -Iseconds)"
}
EOF

    log_maintenance "SUCCESS" "Maintenance report generated: $report_file"
}

# Function to send maintenance notifications
send_maintenance_notifications() {
    if [ $MAINTENANCE_ERRORS -gt 0 ]; then
        log_maintenance "ERROR" "MAINTENANCE ALERT: $MAINTENANCE_ERRORS errors during maintenance"
        # Could integrate with alerting system here
    elif [ $MAINTENANCE_WARNINGS -gt 0 ]; then
        log_maintenance "WARNING" "MAINTENANCE NOTICE: $MAINTENANCE_WARNINGS warnings during maintenance"
    else
        log_maintenance "SUCCESS" "Maintenance completed successfully"
    fi
}

# Main execution
main() {
    log_maintenance "INFO" "Starting automated maintenance for $ENVIRONMENT environment (type: $MAINTENANCE_TYPE)"

    # Perform maintenance based on type
    case "$MAINTENANCE_TYPE" in
        daily)
            log_rotation_and_cleanup
            dependency_security_updates
            database_and_filesystem_optimization
            certificate_renewal
            system_integrity_check
            maintenance_backup
            ;;
        weekly)
            system_package_updates
            # Full maintenance
            log_rotation_and_cleanup
            dependency_security_updates
            database_and_filesystem_optimization
            certificate_renewal
            system_integrity_check
            maintenance_backup
            ;;
        security)
            dependency_security_updates
            system_integrity_check
            ;;
        cleanup)
            log_rotation_and_cleanup
            database_and_filesystem_optimization
            ;;
        *)
            log_maintenance "ERROR" "Unknown maintenance type: $MAINTENANCE_TYPE"
            exit 1
            ;;
    esac

    # Generate report
    generate_maintenance_report

    # Send notifications
    send_maintenance_notifications

    # Final status
    if [ $MAINTENANCE_ERRORS -eq 0 ]; then
        echo -e "${GREEN}🎉 Automated maintenance completed successfully${NC}"
        echo -e "${BLUE}📊 Operations: $MAINTENANCE_SUCCESS successful, $MAINTENANCE_WARNINGS warnings${NC}"
    else
        echo -e "${RED}❌ Automated maintenance completed with $MAINTENANCE_ERRORS errors${NC}"
        echo -e "${YELLOW}⚠️  Check logs for details: $MAINTENANCE_LOG${NC}"
        exit 1
    fi

    log_maintenance "INFO" "Automated maintenance completed"
}

# Parse command line arguments
case "${1:-help}" in
    daily|weekly|security|cleanup)
        main "$@"
        ;;
    help|*)
        echo -e "${BLUE}Automated Maintenance Script for Polymarket Copy Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <maintenance_type> [environment]"
        echo ""
        echo -e "${YELLOW}Maintenance Types:${NC}"
        echo "  daily   - Daily maintenance (logs, security, optimization)"
        echo "  weekly  - Weekly maintenance (includes system updates)"
        echo "  security - Security-focused maintenance only"
        echo "  cleanup - Cleanup operations only"
        echo ""
        echo -e "${YELLOW}Environments:${NC}"
        echo "  production  - Production environment (default)"
        echo "  staging     - Staging environment"
        echo "  development - Development environment"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  $0 daily production"
        echo "  $0 weekly staging"
        echo "  $0 security"
        echo ""
        echo -e "${YELLOW}Cron Job Examples:${NC}"
        echo "  # Daily maintenance at 2 AM"
        echo "  0 2 * * * /path/to/polymarket-copy-bot/scripts/automated_maintenance.sh daily production"
        echo ""
        echo "  # Weekly maintenance Sundays at 3 AM"
        echo "  0 3 * * 0 /path/to/polymarket-copy-bot/scripts/automated_maintenance.sh weekly production"
        exit 0
        ;;
esac
