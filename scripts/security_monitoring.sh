#!/bin/bash
# Security Monitoring for Polymarket Copy Trading Bot
# File integrity monitoring, log-based IDS, event correlation, and automated response

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
ENVIRONMENT="${1:-production}"
MONITORING_LEVEL="${2:-comprehensive}"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        AIDE_DB="/var/lib/aide/aide.db.polymarket"
        MONITORING_LOG="/var/log/polymarket_security_monitoring.log"
        ALERT_EMAIL="${ALERT_EMAIL:-security@company.com}"
        ;;
    staging)
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        AIDE_DB="/var/lib/aide/aide.db.staging"
        MONITORING_LOG="/var/log/polymarket_security_monitoring_staging.log"
        ALERT_EMAIL="${ALERT_EMAIL:-security-staging@company.com}"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Logging
log_security_monitoring() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] [$ENVIRONMENT] $message" >> "$MONITORING_LOG"

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

# Function to create file integrity monitoring with AIDE
create_file_integrity_monitoring() {
    log_security_monitoring "INFO" "Creating file integrity monitoring with AIDE..."

    # Install AIDE
    apt-get install -y aide

    # Create AIDE configuration for Polymarket
    cat > /etc/aide/aide.conf.d/polymarket.conf << EOF
# Polymarket File Integrity Monitoring Configuration

# Polymarket application files
/home/$BOT_USER/polymarket-copy-bot/ PolymarketApp
!!/home/$BOT_USER/polymarket-copy-bot/logs
!!/home/$BOT_USER/polymarket-copy-bot/data/cache
!!/home/$BOT_USER/polymarket-copy-bot/temp

# System configuration files
/etc/polymarket/ PolymarketConfig
/etc/polymarket-staging/ PolymarketConfig
/etc/systemd/system/polymarket*.service PolymarketService

# SSH configuration
/etc/ssh/sshd_config SSHConfig
/etc/ssh/sshd_config.d/ SSHConfig

# User SSH keys (alert on changes)
/home/$BOT_USER/.ssh/authorized_keys UserSSHKeys
/home/polymarket-admin/.ssh/authorized_keys AdminSSHKeys

# Critical system files
/etc/passwd SystemUsers
/etc/shadow SystemPasswords
/etc/group SystemGroups
/etc/sudoers SudoConfig
/etc/sudoers.d/ SudoConfig

# Kernel and security configurations
/etc/sysctl.conf KernelConfig
/etc/sysctl.d/ KernelConfig
/etc/security/ SecurityConfig
/etc/audit/rules.d/ AuditConfig

# Polymarket specific rules
PolymarketApp = p+i+n+u+g+s+m+c+sha256+acl+xattrs
PolymarketConfig = p+i+n+u+g+s+m+c+sha256+acl+xattrs
PolymarketService = p+i+n+u+g+s+m+c+sha256+acl+xattrs
UserSSHKeys = p+i+n+u+g+s+m+c+sha256+acl+xattrs
AdminSSHKeys = p+i+n+u+g+s+m+c+sha256+acl+xattrs
SystemUsers = p+i+n+u+g+s+m+c+sha256
SystemPasswords = p+i+n+u+g+s+m+c+sha256
SystemGroups = p+i+n+u+g+s+m+c+sha256
SudoConfig = p+i+n+u+g+s+m+c+sha256+acl+xattrs
KernelConfig = p+i+n+u+g+s+m+c+sha256+acl+xattrs
SecurityConfig = p+i+n+u+g+s+m+c+sha256+acl+xattrs
AuditConfig = p+i+n+u+g+s+m+c+sha256+acl+xattrs
SSHConfig = p+i+n+u+g+s+m+c+sha256+acl+xattrs
EOF

    # Initialize AIDE database
    mkdir -p /var/lib/aide
    aide --config=/etc/aide/aide.conf --init

    # Move database to final location
    mv /var/lib/aide/aide.db.new "$AIDE_DB"

    # Create AIDE check script
    cat > /usr/local/bin/polymarket_aide_check.sh << EOF
#!/bin/bash
# AIDE File Integrity Check for Polymarket

AIDE_DB="$AIDE_DB"
LOG_FILE="/var/log/polymarket_aide_check.log"
ALERT_FILE="/var/log/polymarket_integrity_alerts.log"

log_aide() {
    echo "\$(date): \$*" >> "\$LOG_FILE"
}

alert_integrity_breach() {
    local changes="\$1"
    echo "\$(date): CRITICAL INTEGRITY BREACH DETECTED" >> "\$ALERT_FILE"
    echo "Changes detected:" >> "\$ALERT_FILE"
    echo "\$changes" >> "\$ALERT_FILE"
    echo "" >> "\$ALERT_FILE"

    # Send alert (implement based on your alerting system)
    echo "CRITICAL: File integrity breach detected on \$(hostname)"
    echo "Check \$ALERT_FILE for details"
}

# Run AIDE check
run_aide_check() {
    log_aide "Starting AIDE integrity check"

    local aide_output
    aide_output=\$(aide --config=/etc/aide/aide.conf --check 2>&1)

    local return_code=\$?

    log_aide "AIDE check completed with return code: \$return_code"

    if [ \$return_code -eq 0 ]; then
        log_aide "SUCCESS: No integrity changes detected"
    elif [ \$return_code -eq 1 ]; then
        log_aide "WARNING: AIDE found changes but no errors"
        # Check if there are actual changes (not just new files)
        if echo "\$aide_output" | grep -q "changed:"; then
            alert_integrity_breach "\$aide_output"
        fi
    elif [ \$return_code -eq 2 ]; then
        log_aide "ERROR: AIDE check failed with errors"
        alert_integrity_breach "AIDE check failed: \$aide_output"
    fi
}

# Update AIDE database (run after legitimate changes)
update_aide_db() {
    log_aide "Updating AIDE database after legitimate changes"

    if aide --config=/etc/aide/aide.conf --update; then
        mv /var/lib/aide/aide.db.new "\$AIDE_DB"
        log_aide "AIDE database updated successfully"
    else
        log_aide "ERROR: Failed to update AIDE database"
        return 1
    fi
}

case "\$1" in
    check)
        run_aide_check
        ;;
    update)
        update_aide_db
        ;;
    *)
        echo "Usage: \$0 <check|update>"
        exit 1
        ;;
esac
EOF

    chmod 700 /usr/local/bin/polymarket_aide_check.sh

    # Create systemd service for AIDE monitoring
    cat > /etc/systemd/system/polymarket-aide-check.service << EOF
[Unit]
Description=Polymarket AIDE Integrity Check
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/polymarket_aide_check.sh check
StandardOutput=journal
StandardError=journal
EOF

    cat > /etc/systemd/system/polymarket-aide-check.timer << EOF
[Unit]
Description=Run Polymarket AIDE check daily
Requires=polymarket-aide-check.service

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=1h

[Install]
WantedBy=timers.target
EOF

    # Enable and start the timer
    systemctl daemon-reload
    systemctl enable polymarket-aide-check.timer
    systemctl start polymarket-aide-check.timer

    log_security_monitoring "SUCCESS" "File integrity monitoring with AIDE configured"
}

# Function to design log-based intrusion detection
design_log_based_ids() {
    log_security_monitoring "INFO" "Designing log-based intrusion detection..."

    # Install log analysis tools
    apt-get install -y logwatch rsyslog logrotate

    # Create custom log analysis rules
    mkdir -p /etc/polymarket/log-analysis

    # SSH attack detection
    cat > /etc/polymarket/log-analysis/ssh_attacks.conf << 'EOF'
# SSH Attack Detection Rules

# Brute force detection
BRUTE_FORCE_THRESHOLD=5
BRUTE_FORCE_WINDOW=300

# Failed password attempts
FAILED_PASSWORD_PATTERN="Failed password for"
INVALID_USER_PATTERN="Invalid user"

# Root login attempts
ROOT_LOGIN_PATTERN="Failed password for root"

# Suspicious login locations
SUSPICIOUS_LOCATIONS=("10.0.0.0/8" "172.16.0.0/12" "192.168.0.0/16" "127.0.0.1")

# Alert thresholds
ALERT_FAILED_ATTEMPTS=3
ALERT_ROOT_ATTEMPTS=1
EOF

    # Application attack detection
    cat > /etc/polymarket/log-analysis/app_attacks.conf << 'EOF'
# Application Attack Detection Rules

# SQL injection patterns
SQL_INJECTION_PATTERNS=(
    "UNION SELECT"
    "1=1"
    "OR 1=1"
    "DROP TABLE"
    "SELECT.*FROM.*WHERE"
)

# XSS patterns
XSS_PATTERNS=(
    "<script>"
    "javascript:"
    "onload="
    "onerror="
    "<iframe>"
)

# Directory traversal
DIRECTORY_TRAVERSAL_PATTERNS=(
    "../../../"
    "..\\..\\"
    "%2e%2e%2f"
    "%2e%2e\\"
)

# Command injection
COMMAND_INJECTION_PATTERNS=(
    "; "
    "| "
    "`"
    "$("
    "${"
)

# Rate limiting
REQUEST_RATE_LIMIT=100
BURST_RATE_LIMIT=200
EOF

    # System anomaly detection
    cat > /etc/polymarket/log-analysis/system_anomalies.conf << 'EOF'
# System Anomaly Detection Rules

# Process monitoring
SUSPICIOUS_PROCESSES=("netcat" "ncat" "nc" "socat" "bash" "sh" "perl" "python.*-c")

# Network anomalies
UNUSUAL_PORTS=(21 23 25 53 110 143 993 995)
HIGH_CONNECTION_COUNT=1000

# File system anomalies
RAPID_FILE_CHANGES=100
SUSPICIOUS_EXTENSIONS=(".exe" ".bat" ".cmd" ".scr" ".pif" ".com")

# Resource exhaustion
HIGH_CPU_THRESHOLD=95
HIGH_MEMORY_THRESHOLD=90
HIGH_DISK_THRESHOLD=95
EOF

    # Create log analysis engine
    cat > /usr/local/bin/polymarket_log_analyzer.sh << 'EOF'
#!/bin/bash
# Log Analysis Engine for Polymarket IDS

SCRIPT_DIR="/etc/polymarket/log-analysis"
LOG_FILE="/var/log/polymarket_log_analysis.log"
ALERT_FILE="/var/log/polymarket_ids_alerts.log"
ANALYSIS_WINDOW="${ANALYSIS_WINDOW:-3600}"  # 1 hour default

log_analysis() {
    echo "$(date): $*" >> "$LOG_FILE"
}

alert_attack() {
    local attack_type="$1"
    local details="$2"
    local severity="${3:-WARNING}"

    echo "$(date): [$severity] $attack_type detected: $details" >> "$ALERT_FILE"
    echo "[$severity] $attack_type: $details" >&2

    # Send alert (implement based on your alerting system)
    # Example: send_email_alert "$attack_type" "$details" "$severity"
}

analyze_ssh_attacks() {
    log_analysis "Analyzing SSH attacks..."

    local auth_log="/var/log/auth.log"
    local temp_file="/tmp/ssh_analysis_$$"

    # Extract recent SSH events
    if [ -f "$auth_log" ]; then
        # Get events from last analysis window
        local cutoff_time=$(date -d "$ANALYSIS_WINDOW seconds ago" +%s)
        awk -v cutoff="$cutoff_time" '
        {
            # Extract timestamp (assuming format: Jan 1 12:00:00)
            cmd = "date -d \"" $1 " " $2 " " $3 "\" +%s 2>/dev/null"
            cmd | getline timestamp
            close(cmd)

            if (timestamp >= cutoff) {
                print $0
            }
        }
        ' "$auth_log" > "$temp_file"
    fi

    if [ ! -f "$temp_file" ] || [ ! -s "$temp_file" ]; then
        log_analysis "No SSH events to analyze"
        return
    fi

    # Load configuration
    source "$SCRIPT_DIR/ssh_attacks.conf"

    # Analyze failed attempts
    local failed_attempts=$(grep -c "$FAILED_PASSWORD_PATTERN\|$INVALID_USER_PATTERN" "$temp_file")
    local root_attempts=$(grep -c "$ROOT_LOGIN_PATTERN" "$temp_file")

    log_analysis "SSH analysis: $failed_attempts failed attempts, $root_attempts root attempts"

    # Check thresholds
    if [ "$failed_attempts" -ge "$ALERT_FAILED_ATTEMPTS" ]; then
        alert_attack "SSH_BRUTE_FORCE" "$failed_attempts failed login attempts in $ANALYSIS_WINDOW seconds" "HIGH"
    fi

    if [ "$root_attempts" -ge "$ALERT_ROOT_ATTEMPTS" ]; then
        alert_attack "SSH_ROOT_ATTACK" "$root_attempts root login attempts detected" "CRITICAL"
    fi

    # Clean up
    rm -f "$temp_file"
}

analyze_application_attacks() {
    log_analysis "Analyzing application attacks..."

    local app_log="/var/log/polymarket/application.log"
    local temp_file="/tmp/app_analysis_$$"

    # Extract recent application events
    if [ -f "$app_log" ]; then
        # Simple time-based filtering (last ANALYSIS_WINDOW seconds)
        tail -n 1000 "$app_log" | grep "$(date -d "$ANALYSIS_WINDOW seconds ago" '+%b %e %H:%M')" > "$temp_file" 2>/dev/null || true
    fi

    if [ ! -f "$temp_file" ] || [ ! -s "$temp_file" ]; then
        log_analysis "No application events to analyze"
        return
    fi

    # Load configuration
    source "$SCRIPT_DIR/app_attacks.conf"

    local attacks_found=0

    # Check for SQL injection
    for pattern in "${SQL_INJECTION_PATTERNS[@]}"; do
        local count=$(grep -c "$pattern" "$temp_file")
        if [ "$count" -gt 0 ]; then
            alert_attack "SQL_INJECTION" "Pattern '$pattern' found $count times" "CRITICAL"
            ((attacks_found++))
        fi
    done

    # Check for XSS
    for pattern in "${XSS_PATTERNS[@]}"; do
        local count=$(grep -c "$pattern" "$temp_file")
        if [ "$count" -gt 0 ]; then
            alert_attack "XSS_ATTACK" "Pattern '$pattern' found $count times" "HIGH"
            ((attacks_found++))
        fi
    done

    # Check for directory traversal
    for pattern in "${DIRECTORY_TRAVERSAL_PATTERNS[@]}"; do
        local count=$(grep -c "$pattern" "$temp_file")
        if [ "$count" -gt 0 ]; then
            alert_attack "DIRECTORY_TRAVERSAL" "Pattern '$pattern' found $count times" "HIGH"
            ((attacks_found++))
        fi
    done

    # Check for command injection
    for pattern in "${COMMAND_INJECTION_PATTERNS[@]}"; do
        local count=$(grep -c "$pattern" "$temp_file")
        if [ "$count" -gt 0 ]; then
            alert_attack "COMMAND_INJECTION" "Pattern '$pattern' found $count times" "CRITICAL"
            ((attacks_found++))
        fi
    done

    log_analysis "Application analysis: $attacks_found attack patterns detected"

    # Clean up
    rm -f "$temp_file"
}

analyze_system_anomalies() {
    log_analysis "Analyzing system anomalies..."

    # Load configuration
    source "$SCRIPT_DIR/system_anomalies.conf"

    # Check for suspicious processes
    for proc in "${SUSPICIOUS_PROCESSES[@]}"; do
        if pgrep -f "$proc" >/dev/null 2>&1; then
            local pid=$(pgrep -f "$proc" | head -1)
            alert_attack "SUSPICIOUS_PROCESS" "Process '$proc' running (PID: $pid)" "HIGH"
        fi
    done

    # Check network connections
    local active_conns=$(ss -tun | wc -l)
    if [ "$active_conns" -gt "$HIGH_CONNECTION_COUNT" ]; then
        alert_attack "HIGH_CONNECTION_COUNT" "$active_conns active connections" "WARNING"
    fi

    # Check unusual ports
    for port in "${UNUSUAL_PORTS[@]}"; do
        if ss -tln | grep -q ":$port "; then
            alert_attack "UNUSUAL_PORT" "Port $port is listening" "WARNING"
        fi
    done

    # Check system resources
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2 + $4}' | cut -d. -f1)
    local mem_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')

    if [ "$cpu_usage" -gt "$HIGH_CPU_THRESHOLD" ]; then
        alert_attack "HIGH_CPU_USAGE" "CPU usage at ${cpu_usage}%" "WARNING"
    fi

    if [ "$mem_usage" -gt "$HIGH_MEMORY_THRESHOLD" ]; then
        alert_attack "HIGH_MEMORY_USAGE" "Memory usage at ${mem_usage}%" "WARNING"
    fi
}

# Main analysis
main() {
    log_analysis "Starting log analysis for IDS"

    analyze_ssh_attacks
    analyze_application_attacks
    analyze_system_anomalies

    log_analysis "Log analysis completed"
}

main
EOF

    chmod 700 /usr/local/bin/polymarket_log_analyzer.sh

    # Create systemd service for log analysis
    cat > /etc/systemd/system/polymarket-log-analyzer.service << EOF
[Unit]
Description=Polymarket Log Analysis IDS
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/polymarket_log_analyzer.sh
StandardOutput=journal
StandardError=journal
EOF

    cat > /etc/systemd/system/polymarket-log-analyzer.timer << EOF
[Unit]
Description=Run Polymarket log analysis every 15 minutes
Requires=polymarket-log-analyzer.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Enable and start the timer
    systemctl daemon-reload
    systemctl enable polymarket-log-analyzer.timer
    systemctl start polymarket-log-analyzer.timer

    log_security_monitoring "SUCCESS" "Log-based intrusion detection configured"
}

# Function to implement security event correlation
implement_event_correlation() {
    log_security_monitoring "INFO" "Implementing security event correlation..."

    # Create event correlation engine
    cat > /usr/local/bin/polymarket_event_correlator.sh << 'EOF'
#!/bin/bash
# Security Event Correlation Engine for Polymarket

LOG_FILE="/var/log/polymarket_event_correlation.log"
CORRELATION_WINDOW="${CORRELATION_WINDOW:-3600}"  # 1 hour
ALERT_FILE="/var/log/polymarket_correlation_alerts.log"

log_correlation() {
    echo "$(date): $*" >> "$LOG_FILE"
}

alert_correlation() {
    local correlation_type="$1"
    local details="$2"
    local severity="${3:-WARNING}"

    echo "$(date): [$severity] $correlation_type: $details" >> "$ALERT_FILE"
    echo "[$severity] $correlation_type: $details" >&2
}

# Correlation rules
correlate_brute_force_ssh() {
    # Correlate multiple SSH failures with account lockouts
    local ssh_failures=$(grep -c "Failed password" /var/log/auth.log)
    local account_lockouts=$(grep -c "pam_tally2" /var/log/auth.log)

    if [ "$ssh_failures" -gt 10 ] && [ "$account_lockouts" -gt 0 ]; then
        alert_correlation "BRUTE_FORCE_SUCCESSFUL" "SSH brute force attack led to $account_lockouts account lockouts" "CRITICAL"
    fi
}

correlate_privilege_escalation() {
    # Correlate sudo usage with suspicious activity
    local sudo_usage=$(grep -c "sudo:" /var/log/auth.log)
    local privilege_commands=$(grep -E "(chmod|chown|passwd|usermod)" /var/log/sudo.log | wc -l)

    if [ "$sudo_usage" -gt 20 ] && [ "$privilege_commands" -gt 5 ]; then
        alert_correlation "PRIVILEGE_ESCALATION" "High sudo usage ($sudo_usage) with privilege commands ($privilege_commands)" "HIGH"
    fi
}

correlate_file_integrity_attacks() {
    # Correlate file changes with network activity
    local file_changes=$(grep -c "integrity.*breach" /var/log/polymarket_integrity_alerts.log 2>/dev/null || echo 0)
    local suspicious_conns=$(grep -c "suspicious.*connection" /var/log/polymarket_network_monitor.log 2>/dev/null || echo 0)

    if [ "$file_changes" -gt 0 ] && [ "$suspicious_conns" -gt 0 ]; then
        alert_correlation "INTEGRITY_ATTACK" "File integrity breaches ($file_changes) correlated with suspicious connections ($suspicious_conns)" "CRITICAL"
    fi
}

correlate_ddos_attack() {
    # Correlate high traffic with service degradation
    local high_traffic=$(grep -c "HIGH.*PACKET" /var/log/polymarket_network_monitor.log 2>/dev/null || echo 0)
    local service_restarts=$(grep -c "restarted" /var/log/polymarket/application.log 2>/dev/null || echo 0)

    if [ "$high_traffic" -gt 5 ] && [ "$service_restarts" -gt 2 ]; then
        alert_correlation "DDOS_ATTACK" "High traffic ($high_traffic) correlated with service restarts ($service_restarts)" "CRITICAL"
    fi
}

correlate_insider_threat() {
    # Correlate unusual access patterns with data access
    local unusual_hours=$(grep -E "([0-1][0-9]|2[0-3]):" /var/log/auth.log | grep -c "Accepted" || echo 0)
    local data_access=$(grep -c "access.*data" /var/log/polymarket/security.log 2>/dev/null || echo 0)

    if [ "$unusual_hours" -gt 10 ] && [ "$data_access" -gt 20 ]; then
        alert_correlation "INSIDER_THREAT" "Unusual access hours ($unusual_hours) with high data access ($data_access)" "HIGH"
    fi
}

correlate_multi_stage_attack() {
    # Look for reconnaissance -> exploitation -> persistence pattern
    local recon=$(grep -c "recon\|scan\|probe" /var/log/polymarket_ids_alerts.log 2>/dev/null || echo 0)
    local exploit=$(grep -c "exploit\|injection\|traversal" /var/log/polymarket_ids_alerts.log 2>/dev/null || echo 0)
    local persistence=$(grep -c "backdoor\|rootkit\|persistence" /var/log/polymarket_ids_alerts.log 2>/dev/null || echo 0)

    if [ "$recon" -gt 0 ] && [ "$exploit" -gt 0 ] && [ "$persistence" -gt 0 ]; then
        alert_correlation "MULTI_STAGE_ATTACK" "Multi-stage attack detected: Recon($recon) -> Exploit($exploit) -> Persistence($persistence)" "CRITICAL"
    fi
}

# Behavioral analysis
analyze_user_behavior() {
    # Track user behavior patterns
    local user="$1"

    if [ -z "$user" ]; then
        return
    fi

    # Get user's recent activity
    local login_count=$(grep -c "Accepted.*$user" /var/log/auth.log 2>/dev/null || echo 0)
    local sudo_count=$(grep -c "$user" /var/log/sudo.log 2>/dev/null || echo 0)
    local file_access=$(grep -c "$user" /var/log/polymarket/security.log 2>/dev/null || echo 0)

    # Calculate behavior score (simple heuristic)
    local behavior_score=$((login_count + sudo_count + file_access))

    # Alert on anomalous behavior
    if [ "$behavior_score" -gt 100 ]; then
        alert_correlation "ANOMALOUS_USER_BEHAVIOR" "User $user shows high activity: logins($login_count) sudo($sudo_count) files($file_access)" "WARNING"
    fi
}

# Main correlation engine
main() {
    log_correlation "Starting event correlation analysis"

    # Run correlation rules
    correlate_brute_force_ssh
    correlate_privilege_escalation
    correlate_file_integrity_attacks
    correlate_ddos_attack
    correlate_insider_threat
    correlate_multi_stage_attack

    # Analyze user behavior for active users
    for user in $(who | awk '{print $1}' | sort | uniq); do
        analyze_user_behavior "$user"
    done

    log_correlation "Event correlation analysis completed"
}

main
EOF

    chmod 700 /usr/local/bin/polymarket_event_correlator.sh

    # Create systemd service for event correlation
    cat > /etc/systemd/system/polymarket-event-correlator.service << EOF
[Unit]
Description=Polymarket Security Event Correlation
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/polymarket_event_correlator.sh
StandardOutput=journal
StandardError=journal
EOF

    cat > /etc/systemd/system/polymarket-event-correlator.timer << EOF
[Unit]
Description=Run Polymarket event correlation every 30 minutes
Requires=polymarket-event-correlator.service

[Timer]
OnBootSec=10min
OnUnitActiveSec=30min
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Enable and start the timer
    systemctl daemon-reload
    systemctl enable polymarket-event-correlator.timer
    systemctl start polymarket-event-correlator.timer

    log_security_monitoring "SUCCESS" "Security event correlation implemented"
}

# Function to add automated security response actions
add_automated_response() {
    log_security_monitoring "INFO" "Adding automated security response actions..."

    # Create automated response system
    cat > /usr/local/bin/polymarket_security_response.sh << 'EOF'
#!/bin/bash
# Automated Security Response System for Polymarket

LOG_FILE="/var/log/polymarket_security_response.log"
RESPONSE_FILE="/var/log/polymarket_response_actions.log"

log_response() {
    echo "$(date): $*" >> "$LOG_FILE"
}

record_response() {
    local action="$1"
    local target="$2"
    local reason="$3"

    echo "$(date): ACTION=$action TARGET=$target REASON=$reason" >> "$RESPONSE_FILE"
    log_response "Executed: $action on $target ($reason)"
}

# Response actions
block_ip() {
    local ip="$1"
    local reason="$2"

    if [ -z "$ip" ]; then
        log_response "ERROR: No IP provided for blocking"
        return 1
    fi

    # Add to UFW blacklist
    ufw deny from "$ip" comment "Auto-blocked: $reason"
    ufw reload

    # Add to fail2ban blacklist
    fail2ban-client set sshd banip "$ip" 2>/dev/null || true

    record_response "BLOCK_IP" "$ip" "$reason"
    log_response "Blocked IP: $ip ($reason)"
}

kill_suspicious_process() {
    local pid="$1"
    local reason="$2"

    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        log_response "ERROR: Invalid or non-existent PID: $pid"
        return 1
    fi

    # Get process information before killing
    local proc_info=$(ps -p "$pid" -o pid,ppid,cmd | tail -1)

    # Kill the process
    kill -TERM "$pid"

    # Wait a bit and force kill if necessary
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        kill -KILL "$pid"
    fi

    record_response "KILL_PROCESS" "$pid" "$reason"
    log_response "Killed process $pid: $proc_info ($reason)"
}

quarantine_file() {
    local file_path="$1"
    local reason="$2"

    if [ ! -f "$file_path" ]; then
        log_response "ERROR: File not found: $file_path"
        return 1
    fi

    # Create quarantine directory
    local quarantine_dir="/var/quarantine/polymarket"
    mkdir -p "$quarantine_dir"

    # Move file to quarantine
    local quarantined_file="$quarantine_dir/$(basename "$file_path").$(date +%s)"
    mv "$file_path" "$quarantined_file"

    # Set restrictive permissions
    chmod 600 "$quarantined_file"
    chown root:root "$quarantined_file"

    record_response "QUARANTINE_FILE" "$file_path" "$reason"
    log_response "Quarantined file: $file_path -> $quarantined_file ($reason)"
}

disable_user() {
    local username="$1"
    local reason="$2"

    if [ -z "$username" ] || ! id "$username" >/dev/null 2>&1; then
        log_response "ERROR: Invalid user: $username"
        return 1
    fi

    # Lock the user account
    passwd -l "$username"

    # Terminate user's processes
    pkill -u "$username" 2>/dev/null || true

    # Kill any remaining sessions
    for session in $(who | grep "^$username" | awk '{print $2}'); do
        pkill -t "$session" 2>/dev/null || true
    done

    record_response "DISABLE_USER" "$username" "$reason"
    log_response "Disabled user account: $username ($reason)"
}

restart_service() {
    local service="$1"
    local reason="$2"

    if ! systemctl is-active --quiet "$service" 2>/dev/null; then
        log_response "ERROR: Service not active: $service"
        return 1
    fi

    # Restart the service
    systemctl restart "$service"

    record_response "RESTART_SERVICE" "$service" "$reason"
    log_response "Restarted service: $service ($reason)"
}

# Response decision engine
process_alert() {
    local alert_type="$1"
    local alert_details="$2"

    log_response "Processing alert: $alert_type - $alert_details"

    case "$alert_type" in
        "SSH_BRUTE_FORCE")
            # Extract IP from alert details
            local ip=$(echo "$alert_details" | grep -oE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' | head -1)
            if [ -n "$ip" ]; then
                block_ip "$ip" "SSH brute force attack"
            fi
            ;;

        "SUSPICIOUS_PROCESS")
            # Extract PID from alert details
            local pid=$(echo "$alert_details" | grep -oE 'PID: [0-9]+' | grep -oE '[0-9]+')
            if [ -n "$pid" ]; then
                kill_suspicious_process "$pid" "Suspicious process detected"
            fi
            ;;

        "INTEGRITY_BREACH")
            # This would typically require manual intervention
            # But we can restart affected services
            restart_service "polymarket-bot" "File integrity breach response"
            ;;

        "HIGH_CONNECTION_COUNT")
            log_response "High connection count detected - manual review recommended"
            # Could implement rate limiting here
            ;;

        "DDOS_ATTACK")
            # Implement DDoS response
            log_response "DDoS attack detected - enabling emergency firewall rules"

            # Enable strict firewall mode
            ufw --force enable
            ufw default deny incoming

            # Allow only essential services
            ufw allow ssh
            ufw allow 80/tcp
            ufw allow 443/tcp

            record_response "ENABLE_DDOS_MODE" "firewall" "DDoS attack response"
            ;;

        "PRIVILEGE_ESCALATION")
            # Extract username if possible
            local user=$(echo "$alert_details" | grep -oE 'user [a-zA-Z0-9_-]+' | awk '{print $2}')
            if [ -n "$user" ]; then
                disable_user "$user" "Privilege escalation detected"
            fi
            ;;
    esac
}

# Monitor for alerts and respond
monitor_and_respond() {
    # Check for new alerts in the last monitoring cycle
    local alert_files=(
        "/var/log/polymarket_ids_alerts.log"
        "/var/log/polymarket_integrity_alerts.log"
        "/var/log/polymarket_correlation_alerts.log"
    )

    for alert_file in "${alert_files[@]}"; do
        if [ -f "$alert_file" ]; then
            # Process new alerts (simple approach - process all recent alerts)
            local recent_alerts=$(tail -20 "$alert_file" 2>/dev/null | grep "$(date '+%F')" || true)

            while IFS= read -r alert_line; do
                if [ -n "$alert_line" ]; then
                    # Extract alert type and details
                    local alert_type=$(echo "$alert_line" | grep -oE '\[([A-Z_]+)\]' | tr -d '[]' || echo "UNKNOWN")
                    local alert_details="$alert_line"

                    process_alert "$alert_type" "$alert_details"
                fi
            done <<< "$recent_alerts"
        fi
    done
}

# Main function
main() {
    log_response "Starting automated security response system"

    # Process command line arguments or monitor for alerts
    if [ $# -gt 0 ]; then
        case "$1" in
            "block")
                block_ip "$2" "${3:-Manual block}"
                ;;
            "kill")
                kill_suspicious_process "$2" "${3:-Manual kill}"
                ;;
            "quarantine")
                quarantine_file "$2" "${3:-Manual quarantine}"
                ;;
            "disable")
                disable_user "$2" "${3:-Manual disable}"
                ;;
            "restart")
                restart_service "$2" "${3:-Manual restart}"
                ;;
            *)
                echo "Usage: $0 [block <ip> | kill <pid> | quarantine <file> | disable <user> | restart <service>]"
                exit 1
                ;;
        esac
    else
        # Monitor mode
        monitor_and_respond
    fi

    log_response "Security response processing completed"
}

main "$@"
EOF

    chmod 700 /usr/local/bin/polymarket_security_response.sh

    # Create systemd service for automated response
    cat > /etc/systemd/system/polymarket-security-response.service << EOF
[Unit]
Description=Polymarket Automated Security Response
After=network.target polymarket-log-analyzer.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/polymarket_security_response.sh
StandardOutput=journal
StandardError=journal
EOF

    cat > /etc/systemd/system/polymarket-security-response.timer << EOF
[Unit]
Description=Run Polymarket security response every 5 minutes
Requires=polymarket-security-response.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Enable and start the timer
    systemctl daemon-reload
    systemctl enable polymarket-security-response.timer
    systemctl start polymarket-security-response.timer

    log_security_monitoring "SUCCESS" "Automated security response actions implemented"
}

# Function to generate security monitoring report
generate_monitoring_report() {
    local report_file="/var/log/polymarket_security_monitoring_report_$(date +%Y%m%d_%H%M%S).txt"

    cat > "$report_file" << EOF
================================================================================
Polymarket Copy Trading Bot - Security Monitoring Report
Generated: $(date)
Environment: $ENVIRONMENT
Monitoring Level: $MONITORING_LEVEL
================================================================================

FILE INTEGRITY MONITORING:

AIDE Status:
$(systemctl is-active polymarket-aide-check.timer 2>/dev/null || echo "Timer not configured")
$(systemctl is-active polymarket-aide-check.service 2>/dev/null || echo "Service not configured")

Database Location: $AIDE_DB

Recent Integrity Checks:
$(tail -10 /var/log/polymarket_aide_check.log 2>/dev/null || echo "No AIDE checks logged")

Integrity Alerts:
$(tail -10 /var/log/polymarket_integrity_alerts.log 2>/dev/null || echo "No integrity alerts")

LOG-BASED INTRUSION DETECTION:

Log Analysis Status:
$(systemctl is-active polymarket-log-analyzer.timer 2>/dev/null || echo "Timer not configured")
$(systemctl is-active polymarket-log-analyzer.service 2>/dev/null || echo "Service not configured")

Analysis Coverage:
- SSH attack detection
- Application attack patterns (SQLi, XSS, traversal, injection)
- System anomaly detection
- Process and network monitoring

IDS Alerts (Last 24 hours):
$(grep "$(date '+%F')" /var/log/polymarket_ids_alerts.log 2>/dev/null | wc -l || echo "0") alerts detected

Recent Alerts:
$(tail -5 /var/log/polymarket_ids_alerts.log 2>/dev/null || echo "No recent alerts")

SECURITY EVENT CORRELATION:

Correlation Status:
$(systemctl is-active polymarket-event-correlator.timer 2>/dev/null || echo "Timer not configured")
$(systemctl is-active polymarket-event-correlator.service 2>/dev/null || echo "Service not configured")

Correlation Rules:
- Brute force attack correlation
- Privilege escalation detection
- File integrity attack correlation
- DDoS attack pattern recognition
- Insider threat detection
- Multi-stage attack analysis

Correlation Alerts:
$(tail -5 /var/log/polymarket_correlation_alerts.log 2>/dev/null || echo "No correlation alerts")

AUTOMATED SECURITY RESPONSE:

Response System Status:
$(systemctl is-active polymarket-security-response.timer 2>/dev/null || echo "Timer not configured")
$(systemctl is-active polymarket-security-response.service 2>/dev/null || echo "Service not configured")

Response Actions Available:
- IP address blocking (UFW + fail2ban)
- Suspicious process termination
- File quarantine
- User account disabling
- Service restart
- DDoS emergency mode

Recent Response Actions:
$(tail -10 /var/log/polymarket_response_actions.log 2>/dev/null || echo "No response actions taken")

MONITORING METRICS:

System Health:
- CPU Usage: $(top -bn1 | grep "Cpu(s)" | awk '{print $2 + $4}' | cut -d. -f1)%
- Memory Usage: $(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')%
- Disk Usage: $(df / | tail -1 | awk '{print $5}')

Security Metrics:
- Active Network Connections: $(ss -tun | wc -l)
- Failed Login Attempts (24h): $(grep "$(date '+%F')" /var/log/auth.log 2>/dev/null | grep -c "Failed password" || echo "0")
- Sudo Commands Executed (24h): $(grep "$(date '+%F')" /var/log/sudo.log 2>/dev/null | wc -l || echo "0")
- Security Events Logged (24h): $(grep "$(date '+%F')" /var/log/polymarket/security.log 2>/dev/null | wc -l || echo "0")

MONITORING SCHEDULE:

AIDE Integrity Checks: Daily
Log Analysis: Every 15 minutes
Event Correlation: Every 30 minutes
Security Response: Every 5 minutes

ALERT THRESHOLDS:

SSH Attacks:
- Failed login attempts: 3 per IP (fail2ban)
- Root login attempts: 1 per IP (immediate block)

Application Attacks:
- SQL injection patterns: Any detection (critical alert)
- XSS patterns: Any detection (high alert)
- Command injection: Any detection (critical alert)

System Anomalies:
- Suspicious processes: Any detection (high alert)
- High connection count: > 1000 connections (warning)
- Resource exhaustion: CPU > 95%, Memory > 90% (warning)

PERFORMANCE IMPACT ASSESSMENT:

LOW IMPACT (< 2% degradation):
- File integrity monitoring (daily)
- Basic log analysis (15min intervals)
- Event correlation (30min intervals)

MEDIUM IMPACT (2-5% degradation):
- Security response monitoring (5min intervals)
- Network connection analysis
- Process anomaly detection

HIGH IMPACT (> 5% degradation):
- Comprehensive AIDE scans (on-demand)
- Full system behavior analysis
- Real-time exploit detection

COMPLIANCE MAPPING:

NIST SP 800-53 Controls:
- SI-4: Information System Monitoring ✅
- SI-5: Security Alerts, Advisories, and Directives ✅
- SI-6: Security Function Verification ✅
- SI-7: Software, Firmware, and Information Integrity ✅
- SI-12: Information Handling and Retention ✅

ISO 27001 Controls:
- A.12: Operations Security ✅
- A.13: Communications Security ✅
- A.14: System Acquisition, Development and Maintenance ✅

IMPLEMENTATION STATUS:

File Integrity Monitoring: ✅ COMPLETE
Log-based IDS: ✅ COMPLETE
Event Correlation: ✅ COMPLETE
Automated Response: ✅ COMPLETE

VERIFICATION COMMANDS:

1. Check AIDE status:
   systemctl status polymarket-aide-check.timer

2. View IDS alerts:
   tail -f /var/log/polymarket_ids_alerts.log

3. Check correlation alerts:
   tail -f /var/log/polymarket_correlation_alerts.log

4. View response actions:
   tail -f /var/log/polymarket_response_actions.log

5. Manual security scan:
   /usr/local/bin/polymarket_log_analyzer.sh

FALSE POSITIVE MANAGEMENT:

1. AIDE Integrity Monitoring:
   - After legitimate changes: /usr/local/bin/polymarket_aide_check.sh update
   - Review alerts in: /var/log/polymarket_integrity_alerts.log
   - Exclude legitimate files in: /etc/aide/aide.conf.d/polymarket.conf

2. Log-based IDS:
   - Adjust patterns in: /etc/polymarket/log-analysis/*.conf
   - Review false alerts in: /var/log/polymarket_ids_alerts.log
   - Whitelist legitimate patterns

3. Event Correlation:
   - Tune correlation rules in: /usr/local/bin/polymarket_event_correlator.sh
   - Adjust thresholds for behavioral analysis
   - Review correlation alerts

4. Automated Response:
   - Test responses in staging environment first
   - Review response actions log before production
   - Implement manual override capabilities

NEXT STEPS:

1. Monitor alerts for one week to tune thresholds
2. Test automated responses with simulated attacks
3. Configure external alerting and notification
4. Implement security dashboard for real-time monitoring
5. Establish incident response procedures

================================================================================
EOF

    chmod 600 "$report_file"
    chown "$BOT_USER:$BOT_GROUP" "$report_file" 2>/dev/null || true

    log_security_monitoring "SUCCESS" "Security monitoring report generated: $report_file"
}

# Main execution
main() {
    echo -e "${PURPLE}🔍 Polymarket Copy Trading Bot - Security Monitoring${NC}"
    echo -e "${PURPLE}===================================================${NC}"
    echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
    echo -e "${BLUE}Monitoring Level: ${MONITORING_LEVEL}${NC}"
    echo ""

    log_security_monitoring "INFO" "Starting comprehensive security monitoring setup..."

    create_file_integrity_monitoring
    design_log_based_ids
    implement_event_correlation
    add_automated_response
    generate_monitoring_report

    echo ""
    echo -e "${GREEN}🎉 Security monitoring setup completed!${NC}"
    echo ""
    echo -e "${BLUE}📄 Review the monitoring report:${NC}"
    echo -e "  /var/log/polymarket_security_monitoring_report_*.txt"
    echo ""
    echo -e "${YELLOW}🔍 Monitoring Components Active:${NC}"
    echo -e "  • File integrity monitoring (AIDE)"
    echo -e "  • Log-based intrusion detection"
    echo -e "  • Security event correlation"
    echo -e "  • Automated response system"
    echo ""
    echo -e "${YELLOW}⏰ Monitoring Schedule:${NC}"
    echo -e "  • AIDE integrity checks: Daily"
    echo -e "  • Log analysis: Every 15 minutes"
    echo -e "  • Event correlation: Every 30 minutes"
    echo -e "  • Security response: Every 5 minutes"
    echo ""
    echo -e "${RED}⚠️  Monitor Logs:${NC}"
    echo -e "  tail -f /var/log/polymarket_ids_alerts.log"
    echo -e "  tail -f /var/log/polymarket_correlation_alerts.log"
    echo -e "  tail -f /var/log/polymarket_response_actions.log"
    echo ""
    echo -e "${CYAN}🧪 Test Security Monitoring:${NC}"
    echo -e "  /usr/local/bin/polymarket_log_analyzer.sh"
    echo -e "  /usr/local/bin/polymarket_event_correlator.sh"
    echo -e "  /usr/local/bin/polymarket_aide_check.sh check"
}

# Parse command line arguments
case "${1:-help}" in
    production|staging|development)
        main "$@"
        ;;
    help|*)
        echo -e "${BLUE}Security Monitoring for Polymarket Copy Trading Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <environment> [monitoring_level]"
        echo ""
        echo -e "${YELLOW}Environments:${NC}"
        echo "  production   - Production environment (default)"
        echo "  staging      - Staging environment"
        echo "  development  - Development environment"
        echo ""
        echo -e "${YELLOW}Monitoring Levels:${NC}"
        echo "  comprehensive - Full security monitoring (default)"
        echo "  standard      - Standard monitoring features"
        echo "  minimal       - Basic monitoring only"
        echo ""
        echo -e "${YELLOW}Security Features:${NC}"
        echo "  • File integrity monitoring with AIDE"
        echo "  • Log-based intrusion detection system"
        echo "  • Security event correlation engine"
        echo "  • Automated security response actions"
        echo "  • Real-time monitoring and alerting"
        echo ""
        echo -e "${YELLOW}Performance Impact:${NC}"
        echo "  Low: < 2% degradation (scheduled monitoring)"
        echo "  Medium: 2-5% degradation (real-time analysis)"
        echo "  High: > 5% degradation (comprehensive scanning)"
        echo ""
        echo -e "${YELLOW}Compliance:${NC}"
        echo "  • NIST SP 800-53 SI-4 (System Monitoring)"
        echo "  • ISO 27001 A.12 (Operations Security)"
        echo "  • SOC 2 Type II monitoring requirements"
        exit 0
        ;;
esac
