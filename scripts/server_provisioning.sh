#!/bin/bash
# Production Server Provisioning for Polymarket Copy Trading Bot
# Bare-metal Ubuntu 24.04 LTS hardening and setup

set -e

# Configuration
SERVER_ROLE="${1:-primary}"
ENVIRONMENT="${2:-production}"
ADMIN_USER="${3:-admin}"
SSH_PUB_KEY="${4:-}"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging
LOG_FILE="/var/log/polymarket_provisioning.log"
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}❌ ERROR: $1${NC}" >&2
    log "ERROR: $1"
    exit 1
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
    log "SUCCESS: $1"
}

warn() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
    log "WARNING: $1"
}

info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
    log "INFO: $1"
}

# Pre-flight checks
preflight_checks() {
    info "Running pre-flight checks..."

    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root"
    fi

    # Check Ubuntu version
    if ! grep -q "Ubuntu 24.04" /etc/os-release; then
        error "This script is designed for Ubuntu 24.04 LTS"
    fi

    # Check internet connectivity
    if ! ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1; then
        error "No internet connectivity detected"
    fi

    # Check available disk space (need at least 20GB)
    local available_gb=$(df / | tail -1 | awk '{print int($4/1024/1024)}')
    if [ "$available_gb" -lt 20 ]; then
        error "Insufficient disk space: ${available_gb}GB available (need 20GB+)"
    fi

    success "Pre-flight checks passed"
}

# Update system packages
update_system() {
    info "Updating system packages..."

    # Update package lists
    apt-get update

    # Upgrade system packages (non-interactive)
    DEBIAN_FRONTEND=noninteractive apt-get -y upgrade

    # Install essential packages
    DEBIAN_FRONTEND=noninteractive apt-get -y install \
        curl \
        wget \
        git \
        vim \
        htop \
        iotop \
        sysstat \
        net-tools \
        dnsutils \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release \
        cron \
        logrotate \
        rsyslog \
        auditd \
        audispd-plugins \
        fail2ban \
        unattended-upgrades \
        needrestart

    success "System packages updated"
}

# Configure timezone and locale
configure_locale() {
    info "Configuring timezone and locale..."

    # Set timezone to UTC
    timedatectl set-timezone UTC

    # Configure locale
    locale-gen en_US.UTF-8
    update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

    # Configure NTP
    apt-get install -y ntp
    systemctl enable ntp
    systemctl start ntp

    success "Locale and timezone configured"
}

# Create administrative user
create_admin_user() {
    info "Creating administrative user: $ADMIN_USER"

    # Check if user already exists
    if id "$ADMIN_USER" >/dev/null 2>&1; then
        warn "User $ADMIN_USER already exists"
        return
    fi

    # Create user with sudo privileges
    useradd -m -s /bin/bash -G sudo "$ADMIN_USER"

    # Set password (will be changed on first login)
    echo "$ADMIN_USER:CHANGE_ME_IMMEDIATELY" | chpasswd

    # Force password change on first login
    chage -d 0 "$ADMIN_USER"

    # Setup SSH key if provided
    if [ -n "$SSH_PUB_KEY" ]; then
        mkdir -p "/home/$ADMIN_USER/.ssh"
        echo "$SSH_PUB_KEY" > "/home/$ADMIN_USER/.ssh/authorized_keys"
        chmod 600 "/home/$ADMIN_USER/.ssh/authorized_keys"
        chmod 700 "/home/$ADMIN_USER/.ssh"
        chown -R "$ADMIN_USER:$ADMIN_USER" "/home/$ADMIN_USER/.ssh"
        success "SSH key configured for $ADMIN_USER"
    fi

    success "Administrative user $ADMIN_USER created"
}

# Harden SSH configuration
harden_ssh() {
    info "Hardening SSH configuration..."

    local sshd_config="/etc/ssh/sshd_config"

    # Backup original config
    cp "$sshd_config" "${sshd_config}.backup.$(date +%Y%m%d_%H%M%S)"

    # Apply SSH hardening
    cat > "$sshd_config" << EOF
# SSH Server Configuration - Hardened for Production
Port 22
AddressFamily inet
ListenAddress 0.0.0.0

# Protocol and authentication
Protocol 2
PermitRootLogin no
StrictModes yes
MaxAuthTries 3
MaxSessions 5

# Password authentication
PasswordAuthentication no
PermitEmptyPasswords no
ChallengeResponseAuthentication no

# Public key authentication
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys

# GSSAPI options
GSSAPIAuthentication no
GSSAPICleanupCredentials no

# Kerberos options
KerberosAuthentication no

# Hostbased authentication
HostbasedAuthentication no
IgnoreUserKnownHosts yes
IgnoreRhosts yes

# Login restrictions
AllowUsers $ADMIN_USER polymarket-bot
LoginGraceTime 30
PermitUserEnvironment no

# Connection settings
ClientAliveInterval 300
ClientAliveCountMax 2
TCPKeepAlive yes
UseDNS no

# Logging
LogLevel VERBOSE
SyslogFacility AUTH

# SFTP
Subsystem sftp /usr/lib/openssh/sftp-server -f AUTHPRIV -l INFO
EOF

    # Restart SSH service
    systemctl reload ssh

    success "SSH configuration hardened"
}

# Configure firewall
configure_firewall() {
    info "Configuring UFW firewall..."

    # Install UFW if not present
    apt-get install -y ufw

    # Reset UFW to defaults
    ufw --force reset

    # Set default policies
    ufw default deny incoming
    ufw default allow outgoing

    # Allow SSH (rate limited)
    ufw limit ssh

    # Allow HTTP/HTTPS for monitoring (if needed)
    ufw allow 80/tcp
    ufw allow 443/tcp

    # Allow custom application ports
    ufw allow 8080/tcp  # Web dashboard
    ufw allow 9090/tcp  # Prometheus metrics (if used)

    # Enable firewall
    echo "y" | ufw enable

    success "Firewall configured with UFW"
}

# System hardening
harden_system() {
    info "Applying system hardening..."

    # Disable unnecessary services
    systemctl disable --now avahi-daemon
    systemctl disable --now cups
    systemctl disable --now bluetooth

    # Configure sysctl security parameters
    cat > /etc/sysctl.d/99-security.conf << EOF
# Network security
net.ipv4.ip_forward=0
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.default.accept_redirects=0
net.ipv4.conf.all.secure_redirects=0
net.ipv4.conf.default.secure_redirects=0
net.ipv4.conf.all.accept_source_route=0
net.ipv4.conf.default.accept_source_route=0
net.ipv4.conf.all.send_redirects=0
net.ipv4.conf.default.send_redirects=0
net.ipv4.conf.all.rp_filter=1
net.ipv4.conf.default.rp_filter=1
net.ipv4.icmp_echo_ignore_broadcasts=1
net.ipv4.icmp_ignore_bogus_error_responses=1
net.ipv4.tcp_syncookies=1
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1

# Kernel security
kernel.dmesg_restrict=1
kernel.kptr_restrict=2
kernel.sysrq=0
kernel.yama.ptrace_scope=1
kernel.core_uses_pid=1
kernel.randomize_va_space=2
kernel.panic=60
kernel.panic_on_oops=60

# Memory security
vm.mmap_min_addr=65536

# File system security
fs.suid_dumpable=0
fs.protected_hardlinks=1
fs.protected_symlinks=1
EOF

    # Apply sysctl settings
    sysctl -p /etc/sysctl.d/99-security.conf

    # Configure PAM security
    # Enforce password complexity
    apt-get install -y libpam-pwquality

    # Configure password policy
    cat > /etc/security/pwquality.conf << EOF
minlen = 12
dcredit = -1
ucredit = -1
lcredit = -1
ocredit = -1
minclass = 4
maxrepeat = 3
dictcheck = 1
EOF

    # Configure account lockout
    cat > /etc/pam.d/common-auth << EOF
auth    required                        pam_tally2.so deny=5 unlock_time=900
auth    [success=1 default=ignore]      pam_unix.so nullok_secure
auth    requisite                       pam_deny.so
auth    required                        pam_permit.so
EOF

    success "System hardening applied"
}

# Configure monitoring and logging
setup_monitoring() {
    info "Setting up monitoring and logging..."

    # Configure auditd for comprehensive auditing
    cat > /etc/audit/rules.d/polymarket.rules << EOF
# Polymarket specific audit rules

# Monitor file access to sensitive files
-w /home/polymarket-bot/ -p rwxa -k polymarket_files
-w /etc/polymarket/ -p rwxa -k polymarket_config

# Monitor network activity
-a always,exit -F arch=b64 -S socket -F a0=2 -k network_socket
-a always,exit -F arch=b32 -S socket -F a0=2 -k network_socket

# Monitor privilege escalation
-w /bin/su -p x -k privilege_escalation
-w /usr/bin/sudo -p x -k privilege_escalation

# Monitor system calls
-a always,exit -F arch=b64 -S execve -k execute
-a always,exit -F arch=b32 -S execve -k execute
EOF

    # Reload audit rules
    augenrules --load

    # Configure logrotate for application logs
    cat > /etc/logrotate.d/polymarket << EOF
/home/polymarket-bot/polymarket-copy-bot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 polymarket-bot polymarket-bot
    postrotate
        systemctl reload polymarket-bot.service || true
    endscript
}
EOF

    # Configure rsyslog for centralized logging
    cat > /etc/rsyslog.d/50-polymarket.conf << EOF
# Polymarket application logging
:programname, startswith, "polymarket" /var/log/polymarket/application.log
& stop

# Security events
:msg, contains, "polymarket" /var/log/polymarket/security.log
& stop
EOF

    # Create log directories
    mkdir -p /var/log/polymarket
    chmod 750 /var/log/polymarket

    # Restart logging services
    systemctl restart rsyslog
    systemctl restart auditd

    success "Monitoring and logging configured"
}

# Configure automatic updates
setup_auto_updates() {
    info "Configuring automatic security updates..."

    # Configure unattended-upgrades
    cat > /etc/apt/apt.conf.d/50unattended-upgrades << EOF
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESM:${distro_codename}";
};

Unattended-Upgrade::Package-Blacklist {
    // Add packages to blacklist if needed
};

Unattended-Upgrade::DevRelease "false";
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::InstallOnShutdown "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-New-Unused-Dependencies "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-Time "02:00";
EOF

    # Enable automatic updates
    cat > /etc/apt/apt.conf.d/20auto-upgrades << EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

    # Enable the service
    systemctl enable unattended-upgrades
    systemctl start unattended-upgrades

    success "Automatic security updates configured"
}

# Setup backup infrastructure
setup_backup_infrastructure() {
    info "Setting up backup infrastructure..."

    # Install backup tools
    apt-get install -y rsync duplicity

    # Create backup directories
    mkdir -p /var/backups/polymarket/{daily,weekly,monthly,offsite}
    chmod 700 /var/backups/polymarket
    chmod 700 /var/backups/polymarket/*

    # Configure backup scripts
    cat > /usr/local/bin/polymarket-backup << EOF
#!/bin/bash
# Polymarket backup script

BACKUP_TYPE="\$1"
BACKUP_DIR="/var/backups/polymarket"
SOURCE_DIR="/home/polymarket-bot"
TIMESTAMP=\$(date +%Y%m%d_%H%M%S)

case "\$BACKUP_TYPE" in
    daily)
        DEST_DIR="\$BACKUP_DIR/daily"
        RETENTION_DAYS=7
        ;;
    weekly)
        DEST_DIR="\$BACKUP_DIR/weekly"
        RETENTION_DAYS=30
        ;;
    monthly)
        DEST_DIR="\$BACKUP_DIR/monthly"
        RETENTION_DAYS=365
        ;;
    *)
        echo "Usage: \$0 {daily|weekly|monthly}"
        exit 1
        ;;
esac

# Create backup
BACKUP_NAME="polymarket_\${BACKUP_TYPE}_\$TIMESTAMP.tar.gz"
tar -czf "\$DEST_DIR/\$BACKUP_NAME" \
    --exclude='*.log' \
    --exclude='cache' \
    --exclude='temp' \
    -C "\$SOURCE_DIR" .

# Set permissions
chmod 600 "\$DEST_DIR/\$BACKUP_NAME"

# Cleanup old backups
find "\$DEST_DIR" -name "polymarket_\${BACKUP_TYPE}_*.tar.gz" -mtime +\$RETENTION_DAYS -delete

echo "Backup completed: \$DEST_DIR/\$BACKUP_NAME"
EOF

    chmod 700 /usr/local/bin/polymarket-backup

    success "Backup infrastructure configured"
}

# Final verification
verify_setup() {
    info "Running final verification..."

    local issues=0

    # Check services
    local services=("ssh" "ufw" "auditd" "rsyslog" "ntp" "unattended-upgrades")
    for service in "${services[@]}"; do
        if ! systemctl is-active --quiet "$service"; then
            warn "Service $service is not running"
            ((issues++))
        fi
    done

    # Check firewall
    if ! ufw status | grep -q "Status: active"; then
        warn "Firewall is not active"
        ((issues++))
    fi

    # Check SSH configuration
    if grep -q "^PermitRootLogin yes" /etc/ssh/sshd_config; then
        warn "SSH root login is still enabled"
        ((issues++))
    fi

    # Check admin user
    if ! id "$ADMIN_USER" >/dev/null 2>&1; then
        warn "Administrative user $ADMIN_USER was not created"
        ((issues++))
    fi

    if [ $issues -eq 0 ]; then
        success "All verification checks passed"
    else
        warn "Found $issues issues during verification"
    fi
}

# Generate deployment report
generate_report() {
    info "Generating deployment report..."

    local report_file="/root/polymarket_provisioning_report_$(date +%Y%m%d_%H%M%S).txt"

    cat > "$report_file" << EOF
================================================================================
Polymarket Copy Trading Bot - Server Provisioning Report
Generated: $(date)
Server Role: $SERVER_ROLE
Environment: $ENVIRONMENT
================================================================================

SYSTEM INFORMATION:
- OS: $(lsb_release -d | cut -f2)
- Kernel: $(uname -r)
- Architecture: $(uname -m)
- Uptime: $(uptime -p)

ADMINISTRATIVE USER:
- Username: $ADMIN_USER
- Home Directory: /home/$ADMIN_USER
- SSH Key Configured: $([ -n "$SSH_PUB_KEY" ] && echo "Yes" || echo "No")

SECURITY CONFIGURATION:
- SSH Root Login: $(grep "^PermitRootLogin" /etc/ssh/sshd_config | cut -d' ' -f2)
- Firewall Status: $(ufw status | grep "Status:" | cut -d' ' -f2)
- Audit System: $(systemctl is-active auditd)
- Automatic Updates: $(systemctl is-active unattended-upgrades)

NETWORK CONFIGURATION:
- SSH Port: $(grep "^Port" /etc/ssh/sshd_config | cut -d' ' -f2)
- Open Ports: $(ufw status numbered | grep ALLOW | wc -l) allowed rules

BACKUP INFRASTRUCTURE:
- Backup Script: /usr/local/bin/polymarket-backup
- Backup Directories: /var/backups/polymarket/{daily,weekly,monthly,offsite}

LOGGING CONFIGURATION:
- Application Logs: /var/log/polymarket/
- Audit Logs: /var/log/audit/
- Log Rotation: Configured for 30 days retention

MONITORING:
- System Monitoring: sysstat enabled
- Security Auditing: auditd enabled
- Log Aggregation: rsyslog configured

NEXT STEPS:
1. Change default password for $ADMIN_USER
2. Configure SSH key authentication
3. Deploy application using deployment script
4. Configure monitoring and alerting
5. Setup backup schedule

================================================================================
EOF

    chmod 600 "$report_file"
    success "Provisioning report generated: $report_file"
}

# Main execution
main() {
    echo -e "${PURPLE}🚀 Polymarket Copy Trading Bot - Server Provisioning${NC}"
    echo -e "${PURPLE}=================================================${NC}"
    echo -e "${BLUE}Server Role: ${SERVER_ROLE}${NC}"
    echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
    echo -e "${BLUE}Admin User: ${ADMIN_USER}${NC}"
    echo ""

    preflight_checks
    update_system
    configure_locale
    create_admin_user
    harden_ssh
    configure_firewall
    harden_system
    setup_monitoring
    setup_auto_updates
    setup_backup_infrastructure
    verify_setup
    generate_report

    echo ""
    echo -e "${GREEN}🎉 Server provisioning completed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}📋 Next Steps:${NC}"
    echo -e "1. Review the provisioning report: /root/polymarket_provisioning_report_*.txt"
    echo -e "2. Change the default password for $ADMIN_USER"
    echo -e "3. Configure SSH key authentication for $ADMIN_USER"
    echo -e "4. Run the application deployment script"
    echo -e "5. Configure monitoring and alerting"
    echo -e "6. Setup regular backup schedule"
    echo ""
    echo -e "${RED}⚠️  IMPORTANT SECURITY REMINDERS:${NC}"
    echo -e "• Change default passwords immediately"
    echo -e "• Never use root login for daily operations"
    echo -e "• Regularly review audit logs"
    echo -e "• Keep system packages updated"
    echo -e "• Monitor firewall rules and SSH access"
    echo ""
    echo -e "${CYAN}📊 System Information:${NC}"
    echo -e "• OS: $(lsb_release -d | cut -f2)"
    echo -e "• Kernel: $(uname -r)"
    echo -e "• Firewall: $(ufw status | grep "Status:" | cut -d' ' -f2)"
    echo -e "• SSH Port: $(grep "^Port" /etc/ssh/sshd_config | cut -d' ' -f2)"
}

# Parse command line arguments
case "${1:-help}" in
    primary|standby|help)
        main "$@"
        ;;
    *)
        echo -e "${BLUE}Server Provisioning Script for Polymarket Copy Trading Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <server_role> [environment] [admin_user] [ssh_pub_key]"
        echo ""
        echo -e "${YELLOW}Server Roles:${NC}"
        echo "  primary  - Primary production server"
        echo "  standby  - Standby/failover server"
        echo ""
        echo -e "${YELLOW}Environments:${NC}"
        echo "  production  - Production environment (default)"
        echo "  staging     - Staging environment"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  $0 primary production admin"
        echo "  $0 standby staging deployer 'ssh-rsa AAAAB3NzaC1yc2E...'"
        echo ""
        echo -e "${YELLOW}Security Features:${NC}"
        echo "  • SSH hardening (no root login, key-only auth)"
        echo "  • UFW firewall configuration"
        echo "  • System hardening (sysctl, PAM)"
        echo "  • Audit logging and monitoring"
        echo "  • Automatic security updates"
        echo "  • Backup infrastructure setup"
        exit 0
        ;;
esac
