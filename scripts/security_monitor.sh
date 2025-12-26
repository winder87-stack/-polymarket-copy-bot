#!/bin/bash
# Security Monitoring Script for Polymarket Copy Bot
# Monitors file integrity, permissions, and suspicious activity

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-production}"
INTEGRITY_DB="$PROJECT_ROOT/security/integrity/file_hashes.db"
AUDIT_LOG="$PROJECT_ROOT/security/audit/filesystem_audit.log"
REPORT_FILE="$PROJECT_ROOT/logs/security_monitor_$(date +%Y%m%d).log"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        ;;
    staging)
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        ;;
    development)
        BOT_USER="${USER:-$(whoami)}"
        BOT_GROUP="${BOT_USER:-$(whoami)}"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Function to log messages
log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] $message" >> "$REPORT_FILE"
    echo "[$timestamp] [$level] $message" >> "$AUDIT_LOG"

    case "$level" in
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
    esac
}

# Function to check file integrity
check_file_integrity() {
    log_message "INFO" "Checking file integrity..."

    if [ ! -f "$INTEGRITY_DB" ]; then
        log_message "ERROR" "Integrity database not found: $INTEGRITY_DB"
        return 1
    fi

    local violations=0
    local total_files=0

    while IFS=':' read -r filename expected_hash timestamp; do
        ((total_files++))
        local filepath="$PROJECT_ROOT/$filename"

        if [ -f "$filepath" ]; then
            local actual_hash=$(sha256sum "$filepath" | awk '{print $1}')

            if [ "$actual_hash" != "$expected_hash" ]; then
                log_message "ERROR" "INTEGRITY VIOLATION: $filename (hash mismatch)"
                log_message "ERROR" "  Expected: $expected_hash"
                log_message "ERROR" "  Actual:   $actual_hash"
                ((violations++))
            else
                log_message "SUCCESS" "Integrity verified: $filename"
            fi
        else
            log_message "ERROR" "FILE MISSING: $filename (recorded in integrity DB)"
            ((violations++))
        fi
    done < "$INTEGRITY_DB"

    log_message "INFO" "Integrity check completed: $total_files files checked, $violations violations"

    return $violations
}

# Function to check file permissions
check_file_permissions() {
    log_message "INFO" "Checking file permissions..."

    local issues=0

    # Define expected permissions for critical directories
    declare -A EXPECTED_DIR_PERMS=(
        ["$PROJECT_ROOT/logs"]="750"
        ["$PROJECT_ROOT/data"]="750"
        ["$PROJECT_ROOT/data/trade_history"]="700"
        ["$PROJECT_ROOT/config"]="750"
        ["$PROJECT_ROOT/security"]="700"
        ["$PROJECT_ROOT/backups"]="700"
    )

    # Check directory permissions
    for dir_path in "${!EXPECTED_DIR_PERMS[@]}"; do
        if [ -d "$dir_path" ]; then
            local actual_perms=$(stat -c "%a" "$dir_path")
            local expected_perms="${EXPECTED_DIR_PERMS[$dir_path]}"

            if [ "$actual_perms" != "$expected_perms" ]; then
                log_message "ERROR" "Wrong permissions on $dir_path: $actual_perms (expected: $expected_perms)"
                ((issues++))
            else
                log_message "SUCCESS" "Correct permissions: $dir_path ($actual_perms)"
            fi
        else
            log_message "WARNING" "Directory not found: $dir_path"
        fi
    done

    # Check critical file permissions
    declare -A EXPECTED_FILE_PERMS=(
        ["$PROJECT_ROOT/.env"]="600"
        ["$PROJECT_ROOT/.env.$ENVIRONMENT"]="600"
        ["$PROJECT_ROOT/config/wallets.json"]="600"
    )

    for file_path in "${!EXPECTED_FILE_PERMS[@]}"; do
        if [ -f "$file_path" ]; then
            local actual_perms=$(stat -c "%a" "$file_path")
            local expected_perms="${EXPECTED_FILE_PERMS[$file_path]}"

            if [ "$actual_perms" != "$expected_perms" ]; then
                log_message "ERROR" "Wrong permissions on $file_path: $actual_perms (expected: $expected_perms)"
                ((issues++))
            else
                log_message "SUCCESS" "Correct permissions: $file_path ($actual_perms)"
            fi
        fi
    done

    log_message "INFO" "Permission check completed: $issues issues found"
    return $issues
}

# Function to check file ownership
check_file_ownership() {
    log_message "INFO" "Checking file ownership..."

    local issues=0

    # Check project ownership
    if [ "$ENVIRONMENT" != "development" ]; then
        local project_owner=$(stat -c "%U:%G" "$PROJECT_ROOT")
        local expected_owner="$BOT_USER:$BOT_GROUP"

        if [ "$project_owner" != "$expected_owner" ]; then
            log_message "ERROR" "Wrong ownership on project directory: $project_owner (expected: $expected_owner)"
            ((issues++))
        else
            log_message "SUCCESS" "Correct project ownership: $project_owner"
        fi
    fi

    # Check critical file ownership
    local critical_files=(
        "$PROJECT_ROOT/.env"
        "$PROJECT_ROOT/.env.$ENVIRONMENT"
        "$PROJECT_ROOT/config/wallets.json"
        "$PROJECT_ROOT/security/integrity/file_hashes.db"
        "$PROJECT_ROOT/security/audit/filesystem_audit.log"
    )

    for file_path in "${critical_files[@]}"; do
        if [ -f "$file_path" ]; then
            if [ "$ENVIRONMENT" != "development" ]; then
                local file_owner=$(stat -c "%U:%G" "$file_path")
                local expected_owner="$BOT_USER:$BOT_GROUP"

                if [ "$file_owner" != "$expected_owner" ]; then
                    log_message "ERROR" "Wrong ownership on $file_path: $file_owner (expected: $expected_owner)"
                    ((issues++))
                fi
            fi
        fi
    done

    log_message "INFO" "Ownership check completed: $issues issues found"
    return $issues
}

# Function to check for suspicious activity
check_suspicious_activity() {
    log_message "INFO" "Checking for suspicious activity..."

    local suspicious_events=0

    # Check for unauthorized access attempts (if audit is available)
    if command -v ausearch >/dev/null 2>&1; then
        # Check for access to sensitive files
        local audit_results=$(ausearch -k polymarket_env -k polymarket_wallets -k polymarket_trades --format text 2>/dev/null | wc -l)

        if [ "$audit_results" -gt 0 ]; then
            log_message "WARNING" "Detected $audit_results audit events for sensitive files"
            # Log the events to our audit log
            ausearch -k polymarket_env -k polymarket_wallets -k polymarket_trades --format text 2>/dev/null >> "$AUDIT_LOG" || true
        fi
    fi

    # Check for unexpected files in sensitive directories
    local unexpected_files=$(find "$PROJECT_ROOT/security" "$PROJECT_ROOT/backups" -type f \( -name "*.exe" -o -name "*.dll" -o -name "*.so" \) 2>/dev/null | wc -l)

    if [ "$unexpected_files" -gt 0 ]; then
        log_message "WARNING" "Found $unexpected_files unexpected executable files in sensitive directories"
        find "$PROJECT_ROOT/security" "$PROJECT_ROOT/backups" -type f \( -name "*.exe" -o -name "*.dll" -o -name "*.so" \) 2>/dev/null | while read -r file; do
            log_message "WARNING" "Unexpected file: $file"
        done
        ((suspicious_events++))
    fi

    # Check for world-writable files
    local world_writable=$(find "$PROJECT_ROOT" -type f -perm -002 2>/dev/null | wc -l)

    if [ "$world_writable" -gt 0 ]; then
        log_message "ERROR" "Found $world_writable world-writable files"
        find "$PROJECT_ROOT" -type f -perm -002 2>/dev/null | while read -r file; do
            log_message "ERROR" "World-writable file: $file"
        done
        ((suspicious_events++))
    fi

    # Check for SUID/SGID files
    local suid_files=$(find "$PROJECT_ROOT" -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | wc -l)

    if [ "$suid_files" -gt 0 ]; then
        log_message "WARNING" "Found $suid_files SUID/SGID files"
        find "$PROJECT_ROOT" -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | while read -r file; do
            log_message "WARNING" "SUID/SGID file: $file"
        done
    fi

    log_message "INFO" "Suspicious activity check completed: $suspicious_events issues found"
    return $suspicious_events
}

# Function to check disk usage
check_disk_usage() {
    log_message "INFO" "Checking disk usage..."

    # Check project directory size
    local project_size=$(du -sh "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    log_message "INFO" "Project directory size: $project_size"

    # Check available space
    local available_space=$(df -h "$PROJECT_ROOT" | tail -1 | awk '{print $4}')
    local usage_percent=$(df "$PROJECT_ROOT" | tail -1 | awk '{print $5}' | sed 's/%//')

    log_message "INFO" "Available disk space: $available_space ($usage_percent% used)"

    if [ "$usage_percent" -gt 90 ]; then
        log_message "ERROR" "Disk usage critically high: $usage_percent%"
        return 1
    elif [ "$usage_percent" -gt 80 ]; then
        log_message "WARNING" "Disk usage high: $usage_percent%"
    fi

    return 0
}

# Function to check running processes
check_running_processes() {
    log_message "INFO" "Checking running processes..."

    # Check if bot is running
    local bot_processes=$(pgrep -f "python.*main.py" | wc -l)

    if [ "$bot_processes" -gt 0 ]; then
        log_message "SUCCESS" "Bot processes running: $bot_processes"
    else
        log_message "WARNING" "No bot processes found running"
    fi

    # Check for unauthorized processes
    local suspicious_procs=$(ps aux | grep -E "(nc|netcat|ncat|socat|ssh.*-R|ssh.*-L)" | grep -v grep | wc -l)

    if [ "$suspicious_procs" -gt 0 ]; then
        log_message "WARNING" "Found $suspicious_procs potentially suspicious processes"
        ps aux | grep -E "(nc|netcat|ncat|socat|ssh.*-R|ssh.*-L)" | grep -v grep >> "$AUDIT_LOG"
    fi
}

# Function to generate security report
generate_report() {
    local total_issues=$1
    local integrity_issues=$2
    local permission_issues=$3
    local ownership_issues=$4
    local suspicious_events=$5

    log_message "INFO" "Generating security report..."

    {
        echo "=========================================="
        echo "Polymarket Copy Bot Security Report"
        echo "Environment: $ENVIRONMENT"
        echo "Generated: $(date)"
        echo "=========================================="
        echo ""
        echo "SUMMARY:"
        echo "  Total Issues: $total_issues"
        echo "  Integrity Violations: $integrity_issues"
        echo "  Permission Issues: $permission_issues"
        echo "  Ownership Issues: $ownership_issues"
        echo "  Suspicious Events: $suspicious_events"
        echo ""
        echo "STATUS: $([ $total_issues -eq 0 ] && echo "SECURE" || echo "ISSUES FOUND")"
        echo ""
        echo "=========================================="
    } >> "$REPORT_FILE"

    echo ""
    echo -e "${BLUE}📊 Security Report Generated: $REPORT_FILE${NC}"

    if [ $total_issues -eq 0 ]; then
        echo -e "${GREEN}🎉 Security check passed - no issues found!${NC}"
    else
        echo -e "${RED}❌ Security check failed - $total_issues issues found${NC}"
        echo -e "${YELLOW}   Review the report for details${NC}"
    fi
}

# Main execution
main() {
    log_message "INFO" "Starting security monitoring for environment: $ENVIRONMENT"

    # Ensure directories exist
    mkdir -p "$(dirname "$REPORT_FILE")"
    mkdir -p "$(dirname "$AUDIT_LOG")"

    # Run all checks
    local integrity_issues=0
    local permission_issues=0
    local ownership_issues=0
    local suspicious_events=0
    local disk_issues=0

    check_file_integrity && ((integrity_issues += $?))
    check_file_permissions && ((permission_issues += $?))
    check_file_ownership && ((ownership_issues += $?))
    check_suspicious_activity && ((suspicious_events += $?))
    check_disk_usage && ((disk_issues += $?))
    check_running_processes

    local total_issues=$((integrity_issues + permission_issues + ownership_issues + suspicious_events + disk_issues))

    generate_report "$total_issues" "$integrity_issues" "$permission_issues" "$ownership_issues" "$suspicious_events"

    # Exit with error code if issues found
    [ $total_issues -eq 0 ]
}

# Run main function
main "$@"
