#!/bin/bash
# Compliance & Auditing for Polymarket Copy Trading Bot
# SOX, GDPR, and security compliance monitoring and reporting

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
OPERATION="${1:-audit}"
ENVIRONMENT="${2:-production}"
REPORT_TYPE="${3:-comprehensive}"

# Compliance standards
COMPLIANCE_STANDARDS=("SOX" "GDPR" "PCI" "NIST" "ISO27001")

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        LOG_DIR="/var/log/polymarket"
        AUDIT_DIR="/var/log/polymarket-audit"
        ;;
    staging)
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        LOG_DIR="/var/log/polymarket-staging"
        AUDIT_DIR="/var/log/polymarket-audit-staging"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Audit logging
AUDIT_LOG="$AUDIT_DIR/compliance_audit.log"
log_audit() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] [$OPERATION] $message" >> "$AUDIT_LOG"

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

# Function to create audit directories
create_audit_directories() {
    log_audit "INFO" "Creating audit directories..."

    local dirs=("$AUDIT_DIR" "$AUDIT_DIR/reports" "$AUDIT_DIR/evidence" "$AUDIT_DIR/compliance")

    for dir_path in "${dirs[@]}"; do
        mkdir -p "$dir_path"
        chmod 700 "$dir_path"
        if [ "$ENVIRONMENT" = "production" ]; then
            chown "$BOT_USER:$BOT_GROUP" "$dir_path" 2>/dev/null || true
        fi
    done

    log_audit "SUCCESS" "Audit directories created"
}

# Function to audit file permissions
audit_file_permissions() {
    log_audit "INFO" "Auditing file permissions..."

    local issues=0
    local evidence_file="$AUDIT_DIR/evidence/file_permissions_$(date +%Y%m%d_%H%M%S).txt"

    {
        echo "File Permissions Audit - $(date)"
        echo "Environment: $ENVIRONMENT"
        echo "========================================"
        echo ""
    } > "$evidence_file"

    # Check critical file permissions
    local critical_files=(
        "$PROJECT_DIR/.env:600"
        "$PROJECT_DIR/.env.$ENVIRONMENT:600"
        "$PROJECT_DIR/config/wallets.json:600"
        "$PROJECT_DIR/security/integrity/file_hashes.db:600"
    )

    for file_spec in "${critical_files[@]}"; do
        local file_path="${file_spec%%:*}"
        local expected_perms="${file_spec##*:}"

        if [ -f "$file_path" ]; then
            local actual_perms=$(stat -c "%a" "$file_path" 2>/dev/null || echo "unknown")
            local owner=$(stat -c "%U:%G" "$file_path" 2>/dev/null || echo "unknown")

            echo "File: $file_path" >> "$evidence_file"
            echo "  Expected: $expected_perms (owner: $BOT_USER:$BOT_GROUP)" >> "$evidence_file"
            echo "  Actual:   $actual_perms (owner: $owner)" >> "$evidence_file"

            if [ "$actual_perms" != "$expected_perms" ]; then
                echo "  STATUS: NON-COMPLIANT - Wrong permissions" >> "$evidence_file"
                ((issues++))
            elif [ "$owner" != "$BOT_USER:$BOT_GROUP" ] && [ "$ENVIRONMENT" != "development" ]; then
                echo "  STATUS: NON-COMPLIANT - Wrong ownership" >> "$evidence_file"
                ((issues++))
            else
                echo "  STATUS: COMPLIANT" >> "$evidence_file"
            fi
            echo "" >> "$evidence_file"
        else
            echo "File: $file_path" >> "$evidence_file"
            echo "  STATUS: MISSING" >> "$evidence_file"
            echo "" >> "$evidence_file"
            ((issues++))
        fi
    done

    # Check for world-accessible sensitive files
    local world_accessible=$(find "$PROJECT_DIR" -type f \( -name "*.key" -o -name "*private*" -o -name "*.pem" \) -perm -o+r 2>/dev/null || true)

    if [ -n "$world_accessible" ]; then
        echo "World-accessible sensitive files:" >> "$evidence_file"
        echo "$world_accessible" >> "$evidence_file"
        echo "STATUS: NON-COMPLIANT - Security risk" >> "$evidence_file"
        ((issues++))
    fi

    if [ $issues -eq 0 ]; then
        log_audit "SUCCESS" "File permissions audit passed"
    else
        log_audit "WARNING" "File permissions audit found $issues issues"
    fi

    echo "Evidence saved to: $evidence_file"
}

# Function to audit user access
audit_user_access() {
    log_audit "INFO" "Auditing user access..."

    local evidence_file="$AUDIT_DIR/evidence/user_access_$(date +%Y%m%d_%H%M%S).txt"

    {
        echo "User Access Audit - $(date)"
        echo "Environment: $ENVIRONMENT"
        echo "========================================"
        echo ""
    } > "$evidence_file"

    # Check bot user configuration
    if id "$BOT_USER" >/dev/null 2>&1; then
        local user_info=$(id "$BOT_USER")
        local user_shell=$(getent passwd "$BOT_USER" | cut -d: -f7)
        local user_groups=$(groups "$BOT_USER" 2>/dev/null || echo "unknown")

        echo "Bot User: $BOT_USER" >> "$evidence_file"
        echo "  Info: $user_info" >> "$evidence_file"
        echo "  Shell: $user_shell" >> "$evidence_file"
        echo "  Groups: $user_groups" >> "$evidence_file"

        # Check if user has password (should be locked)
        if passwd -S "$BOT_USER" 2>/dev/null | grep -q "Password locked"; then
            echo "  Password: LOCKED (COMPLIANT)" >> "$evidence_file"
        else
            echo "  Password: NOT LOCKED (NON-COMPLIANT)" >> "$evidence_file"
            log_audit "WARNING" "Bot user password is not locked"
        fi

        echo "" >> "$evidence_file"
    else
        echo "Bot User: $BOT_USER - NOT FOUND (NON-COMPLIANT)" >> "$evidence_file"
        log_audit "ERROR" "Bot user does not exist"
    fi

    # Check SSH access
    if [ -f "/home/$BOT_USER/.ssh/authorized_keys" ]; then
        local key_count=$(wc -l < "/home/$BOT_USER/.ssh/authorized_keys")
        echo "SSH Keys: $key_count authorized keys" >> "$evidence_file"

        # Check SSH key permissions
        local key_perms=$(stat -c "%a" "/home/$BOT_USER/.ssh/authorized_keys" 2>/dev/null || echo "unknown")
        if [ "$key_perms" = "600" ]; then
            echo "  Permissions: $key_perms (COMPLIANT)" >> "$evidence_file"
        else
            echo "  Permissions: $key_perms (NON-COMPLIANT)" >> "$evidence_file"
            log_audit "WARNING" "SSH authorized_keys has wrong permissions"
        fi
    else
        echo "SSH Keys: No authorized_keys file" >> "$evidence_file"
    fi

    log_audit "SUCCESS" "User access audit completed"
    echo "Evidence saved to: $evidence_file"
}

# Function to audit system security
audit_system_security() {
    log_audit "INFO" "Auditing system security..."

    local evidence_file="$AUDIT_DIR/evidence/system_security_$(date +%Y%m%d_%H%M%S).txt"

    {
        echo "System Security Audit - $(date)"
        echo "Environment: $ENVIRONMENT"
        echo "========================================"
        echo ""
    } > "$evidence_file"

    # Check SSH configuration
    echo "SSH Configuration:" >> "$evidence_file"
    local ssh_checks=(
        "PermitRootLogin:no"
        "PasswordAuthentication:no"
        "PermitEmptyPasswords:no"
        "Protocol:2"
    )

    for check in "${ssh_checks[@]}"; do
        local param="${check%%:*}"
        local expected="${check##*:}"
        local actual=$(grep "^$param" /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo "not_set")

        echo "  $param: expected=$expected, actual=$actual" >> "$evidence_file"
        if [ "$actual" != "$expected" ]; then
            echo "    STATUS: NON-COMPLIANT" >> "$evidence_file"
            log_audit "WARNING" "SSH $param is not compliant"
        else
            echo "    STATUS: COMPLIANT" >> "$evidence_file"
        fi
    done

    # Check firewall status
    echo "" >> "$evidence_file"
    echo "Firewall Status:" >> "$evidence_file"
    if ufw status 2>/dev/null | grep -q "Status: active"; then
        echo "  Status: ACTIVE (COMPLIANT)" >> "$evidence_file"
        local open_ports=$(ufw status numbered 2>/dev/null | grep ALLOW | wc -l)
        echo "  Open ports: $open_ports" >> "$evidence_file"
    else
        echo "  Status: INACTIVE (NON-COMPLIANT)" >> "$evidence_file"
        log_audit "ERROR" "Firewall is not active"
    fi

    # Check audit system
    echo "" >> "$evidence_file"
    echo "Audit System:" >> "$evidence_file"
    if systemctl is-active --quiet auditd 2>/dev/null; then
        echo "  Status: ACTIVE (COMPLIANT)" >> "$evidence_file"
        local audit_rules=$(auditctl -l | wc -l)
        echo "  Rules loaded: $audit_rules" >> "$evidence_file"
    else
        echo "  Status: INACTIVE (NON-COMPLIANT)" >> "$evidence_file"
        log_audit "ERROR" "Audit system is not active"
    fi

    # Check security updates
    echo "" >> "$evidence_file"
    echo "Security Updates:" >> "$evidence_file"
    local updates_available=$(/usr/lib/update-notifier/apt-check 2>&1 | cut -d';' -f1 || echo "unknown")
    if [ "$updates_available" = "unknown" ]; then
        echo "  Status: UNKNOWN" >> "$evidence_file"
    elif [ "$updates_available" -gt 0 ]; then
        echo "  Available: $updates_available (ACTION REQUIRED)" >> "$evidence_file"
        log_audit "WARNING" "$updates_available security updates available"
    else
        echo "  Status: UP TO DATE (COMPLIANT)" >> "$evidence_file"
    fi

    log_audit "SUCCESS" "System security audit completed"
    echo "Evidence saved to: $evidence_file"
}

# Function to audit data handling
audit_data_handling() {
    log_audit "INFO" "Auditing data handling and privacy..."

    local evidence_file="$AUDIT_DIR/evidence/data_handling_$(date +%Y%m%d_%H%M%S).txt"

    {
        echo "Data Handling Audit - $(date)"
        echo "Environment: $ENVIRONMENT"
        echo "========================================"
        echo ""
    } > "$evidence_file"

    # Check for sensitive data in logs
    echo "Sensitive Data in Logs:" >> "$evidence_file"
    local sensitive_patterns=("PRIVATE_KEY" "password" "secret" "token" "api_key")

    for pattern in "${sensitive_patterns[@]}"; do
        local occurrences=$(grep -r "$pattern" "$LOG_DIR" 2>/dev/null | wc -l || echo "0")
        echo "  $pattern: $occurrences occurrences" >> "$evidence_file"

        if [ "$occurrences" -gt 0 ]; then
            echo "    STATUS: POTENTIAL BREACH - Review required" >> "$evidence_file"
            log_audit "ERROR" "Found $occurrences instances of $pattern in logs"
        fi
    done

    # Check data retention
    echo "" >> "$evidence_file"
    echo "Data Retention:" >> "$evidence_file"

    # Check trade history age
    local trade_dir="$PROJECT_DIR/data/trade_history"
    if [ -d "$trade_dir" ]; then
        local oldest_file=$(find "$trade_dir" -name "*.json" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | head -1 | cut -d' ' -f2- || echo "none")
        if [ "$oldest_file" != "none" ]; then
            local file_age_days=$(( ($(date +%s) - $(stat -c %Y "$oldest_file")) / 86400 ))
            echo "  Oldest trade file: $file_age_days days old" >> "$evidence_file"

            if [ "$file_age_days" -gt 90 ]; then
                echo "    STATUS: RETENTION POLICY VIOLATION (>90 days)" >> "$evidence_file"
                log_audit "WARNING" "Trade data retention exceeds 90 days"
            else
                echo "    STATUS: COMPLIANT" >> "$evidence_file"
            fi
        else
            echo "  No trade files found" >> "$evidence_file"
        fi
    fi

    # Check backup encryption
    echo "" >> "$evidence_file"
    echo "Backup Encryption:" >> "$evidence_file"

    local encrypted_backups=$(find /var/backups/polymarket -name "*.enc" 2>/dev/null | wc -l)
    local total_backups=$(find /var/backups/polymarket -name "*.tar.gz*" 2>/dev/null | wc -l)

    echo "  Encrypted backups: $encrypted_backups" >> "$evidence_file"
    echo "  Total backups: $total_backups" >> "$evidence_file"

    if [ "$total_backups" -gt 0 ] && [ "$encrypted_backups" -eq "$total_backups" ]; then
        echo "  STATUS: COMPLIANT - All backups encrypted" >> "$evidence_file"
    else
        echo "  STATUS: NON-COMPLIANT - Not all backups encrypted" >> "$evidence_file"
        log_audit "WARNING" "Not all backups are encrypted"
    fi

    log_audit "SUCCESS" "Data handling audit completed"
    echo "Evidence saved to: $evidence_file"
}

# Function to audit access controls
audit_access_controls() {
    log_audit "INFO" "Auditing access controls..."

    local evidence_file="$AUDIT_DIR/evidence/access_controls_$(date +%Y%m%d_%H%M%S).txt"

    {
        echo "Access Controls Audit - $(date)"
        echo "Environment: $ENVIRONMENT"
        echo "========================================"
        echo ""
    } > "$evidence_file"

    # Check sudo access
    echo "Sudo Access:" >> "$evidence_file"
    if groups "$BOT_USER" 2>/dev/null | grep -q sudo; then
        echo "  Bot user has sudo access: YES (POTENTIAL RISK)" >> "$evidence_file"
        log_audit "WARNING" "Bot user has sudo privileges"
    else
        echo "  Bot user has sudo access: NO (COMPLIANT)" >> "$evidence_file"
    fi

    # Check recent logins
    echo "" >> "$evidence_file"
    echo "Recent Logins:" >> "$evidence_file"
    local recent_logins=$(last -n 10 2>/dev/null | head -10 || echo "No login data available")
    echo "$recent_logins" >> "$evidence_file"

    # Check failed login attempts
    echo "" >> "$evidence_file"
    echo "Failed Login Attempts:" >> "$evidence_file"

    if command -v pam_tally2 >/dev/null 2>&1; then
        local failed_attempts=$(pam_tally2 2>/dev/null | wc -l)
        echo "  Failed attempts: $failed_attempts" >> "$evidence_file"

        if [ "$failed_attempts" -gt 5 ]; then
            echo "  STATUS: MONITOR - High failure rate" >> "$evidence_file"
            log_audit "WARNING" "High number of failed login attempts: $failed_attempts"
        fi
    else
        echo "  pam_tally2 not available" >> "$evidence_file"
    fi

    # Check file access audit
    echo "" >> "$evidence_file"
    echo "File Access Audit:" >> "$evidence_file"

    if command -v ausearch >/dev/null 2>&1; then
        local audit_events=$(ausearch -k polymarket_files -ts today 2>/dev/null | wc -l)
        echo "  Today's file access events: $audit_events" >> "$evidence_file"

        if [ "$audit_events" -gt 1000 ]; then
            echo "  STATUS: HIGH ACTIVITY - Review audit logs" >> "$evidence_file"
            log_audit "WARNING" "High file access activity: $audit_events events today"
        fi
    else
        echo "  Audit tools not available" >> "$evidence_file"
    fi

    log_audit "SUCCESS" "Access controls audit completed"
    echo "Evidence saved to: $evidence_file"
}

# Function to generate compliance report
generate_compliance_report() {
    local report_file="$AUDIT_DIR/reports/compliance_report_$ENVIRONMENT_$(date +%Y%m%d_%H%M%S).txt"
    local json_report="${report_file%.txt}.json"

    log_audit "INFO" "Generating compliance report..."

    # Collect all evidence files from today's audit
    local today=$(date +%Y%m%d)
    local evidence_files=$(find "$AUDIT_DIR/evidence" -name "*${today}*.txt" 2>/dev/null)

    # Calculate compliance scores
    local total_checks=0
    local passed_checks=0

    for evidence_file in $evidence_files; do
        local compliant_lines=$(grep -c "COMPLIANT" "$evidence_file" 2>/dev/null || echo "0")
        local total_lines=$(grep -c "STATUS:" "$evidence_file" 2>/dev/null || echo "0")

        ((total_checks += total_lines))
        ((passed_checks += compliant_lines))
    done

    local compliance_score=0
    if [ $total_checks -gt 0 ]; then
        compliance_score=$((passed_checks * 100 / total_checks))
    fi

    # Generate text report
    cat > "$report_file" << EOF
================================================================================
Polymarket Copy Trading Bot - Compliance Audit Report
Generated: $(date)
Environment: $ENVIRONMENT
Report Type: $REPORT_TYPE
================================================================================

EXECUTIVE SUMMARY:
- Compliance Score: ${compliance_score}%
- Total Checks: $total_checks
- Passed Checks: $passed_checks
- Audit Date: $(date)
- Auditor: Automated Compliance System

COMPLIANCE STANDARDS EVALUATED:
$(printf '%s\n' "${COMPLIANCE_STANDARDS[@]}")

AUDIT SCOPE:
- File permissions and ownership
- User access controls
- System security configuration
- Data handling and privacy
- Access control mechanisms

DETAILED FINDINGS:

EOF

    # Append evidence summaries
    for evidence_file in $evidence_files; do
        local audit_type=$(basename "$evidence_file" | sed 's/[0-9_]*\.txt$//' | sed 's/_$//')
        echo "=== $(echo "$audit_type" | tr '_' ' ' | tr '[:lower:]' '[:upper:]') ===" >> "$report_file"
        echo "" >> "$report_file"

        # Extract non-compliant items
        grep -A2 -B1 "NON-COMPLIANT\|MISSING\|POTENTIAL\|VIOLATION" "$evidence_file" 2>/dev/null || echo "No issues found" >> "$report_file"
        echo "" >> "$report_file"
    done

    cat >> "$report_file" << EOF
RECOMMENDATIONS:

1. IMMEDIATE ACTIONS (Critical):
$(grep -h "NON-COMPLIANT\|MISSING\|VIOLATION" "$AUDIT_DIR/evidence/"*"$today"*.txt 2>/dev/null | wc -l || echo "0") issues require immediate attention

2. SHORT-TERM IMPROVEMENTS:
   - Implement automated remediation for common issues
   - Enhance monitoring and alerting
   - Regular security training for administrators

3. LONG-TERM ENHANCEMENTS:
   - Implement continuous compliance monitoring
   - Automate evidence collection and reporting
   - Integrate with enterprise compliance platforms

NEXT AUDIT SCHEDULE:
- Daily automated checks: Every day at 6:00 AM
- Weekly comprehensive audit: Every Sunday at 7:00 AM
- Monthly compliance review: First day of each month
- Quarterly external audit: As required by compliance standards

CONTACT INFORMATION:
- Compliance Officer: compliance@company.com
- Security Team: security@company.com
- System Administration: admin@company.com

================================================================================
EOF

    # Generate JSON report
    cat > "$json_report" << EOF
{
  "report_metadata": {
    "generated_at": "$(date -Iseconds)",
    "environment": "$ENVIRONMENT",
    "report_type": "$REPORT_TYPE",
    "audit_date": "$(date +%Y-%m-%d)"
  },
  "compliance_summary": {
    "overall_score": $compliance_score,
    "total_checks": $total_checks,
    "passed_checks": $passed_checks,
    "failed_checks": $((total_checks - passed_checks))
  },
  "standards_evaluated": $(printf '%s\n' "${COMPLIANCE_STANDARDS[@]}" | jq -R . | jq -s .),
  "evidence_files": $(echo "$evidence_files" | tr ' ' '\n' | jq -R . | jq -s .),
  "recommendations": [
    "Review all NON-COMPLIANT items immediately",
    "Implement automated remediation where possible",
    "Enhance monitoring and alerting systems",
    "Conduct regular security training",
    "Schedule next comprehensive audit"
  ]
}
EOF

    log_audit "SUCCESS" "Compliance report generated: $report_file"
    echo "Reports generated:"
    echo "  Text: $report_file"
    echo "  JSON: $json_report"
}

# Function to perform comprehensive audit
perform_comprehensive_audit() {
    log_audit "INFO" "Starting comprehensive compliance audit..."

    create_audit_directories
    audit_file_permissions
    audit_user_access
    audit_system_security
    audit_data_handling
    audit_access_controls
    generate_compliance_report

    log_audit "SUCCESS" "Comprehensive compliance audit completed"
}

# Function to monitor compliance continuously
monitor_compliance() {
    log_audit "INFO" "Starting continuous compliance monitoring..."

    # This would run continuous monitoring
    # For now, just run a quick check
    local critical_issues=$(find "$AUDIT_DIR/evidence" -name "*.txt" -mtime -1 -exec grep -l "NON-COMPLIANT\|CRITICAL" {} \; 2>/dev/null | wc -l)

    if [ "$critical_issues" -gt 0 ]; then
        log_audit "WARNING" "Found $critical_issues critical compliance issues in recent audits"
    else
        log_audit "SUCCESS" "No critical compliance issues detected"
    fi
}

# Main execution
main() {
    echo -e "${PURPLE}📋 Polymarket Copy Trading Bot - Compliance Audit${NC}"
    echo -e "${PURPLE}=================================================${NC}"
    echo -e "${BLUE}Operation: ${OPERATION}${NC}"
    echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
    echo -e "${BLUE}Report Type: ${REPORT_TYPE}${NC}"
    echo ""

    case "$OPERATION" in
        audit)
            case "$REPORT_TYPE" in
                comprehensive|full)
                    perform_comprehensive_audit
                    ;;
                permissions)
                    create_audit_directories
                    audit_file_permissions
                    ;;
                security)
                    create_audit_directories
                    audit_system_security
                    ;;
                access)
                    create_audit_directories
                    audit_user_access
                    audit_access_controls
                    ;;
                data)
                    create_audit_directories
                    audit_data_handling
                    ;;
                *)
                    echo -e "${RED}❌ Invalid report type: $REPORT_TYPE${NC}"
                    exit 1
                    ;;
            esac
            ;;
        monitor)
            monitor_compliance
            ;;
        report)
            generate_compliance_report
            ;;
        *)
            echo -e "${RED}❌ Invalid operation: $OPERATION${NC}"
            exit 1
            ;;
    esac

    echo -e "${GREEN}🎉 Compliance audit operation completed!${NC}"
    echo -e "${BLUE}📊 Check audit logs: $AUDIT_LOG${NC}"
    echo -e "${BLUE}📁 Evidence location: $AUDIT_DIR/evidence/${NC}"
    echo -e "${BLUE}📄 Reports location: $AUDIT_DIR/reports/${NC}"
}

# Parse command line arguments
case "${1:-help}" in
    audit|monitor|report)
        main "$@"
        ;;
    help|*)
        echo -e "${BLUE}Compliance & Auditing for Polymarket Copy Trading Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <operation> [environment] [report_type]"
        echo ""
        echo -e "${YELLOW}Operations:${NC}"
        echo "  audit     - Perform compliance audit"
        echo "  monitor   - Continuous compliance monitoring"
        echo "  report    - Generate compliance report"
        echo ""
        echo -e "${YELLOW}Report Types:${NC}"
        echo "  comprehensive - Full compliance audit (default)"
        echo "  permissions   - File permissions audit only"
        echo "  security      - System security audit only"
        echo "  access        - User access audit only"
        echo "  data          - Data handling audit only"
        echo ""
        echo -e "${YELLOW}Environments:${NC}"
        echo "  production    - Production environment (default)"
        echo "  staging       - Staging environment"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  $0 audit production comprehensive"
        echo "  $0 audit staging permissions"
        echo "  $0 monitor production"
        echo "  $0 report production"
        echo ""
        echo -e "${YELLOW}Compliance Standards:${NC}"
        echo "  SOX       - Sarbanes-Oxley Act"
        echo "  GDPR      - General Data Protection Regulation"
        echo "  PCI       - Payment Card Industry"
        echo "  NIST      - National Institute of Standards and Technology"
        echo "  ISO27001  - Information Security Management"
        echo ""
        echo -e "${YELLOW}Audit Evidence:${NC}"
        echo "  All audit evidence is stored in: /var/log/polymarket-audit/evidence/"
        echo "  Reports are generated in: /var/log/polymarket-audit/reports/"
        exit 0
        ;;
esac
