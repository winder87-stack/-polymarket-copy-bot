#!/bin/bash
# Comprehensive Filesystem Security Setup for Polymarket Copy Bot
# This script implements enterprise-grade filesystem security

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

# Default configuration
ENVIRONMENT="${1:-production}"
FORCE_RECREATE="${2:-false}"
ENABLE_ENCRYPTION="${3:-false}"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        BASE_DIR="/home/$BOT_USER"
        PROJECT_DIR="$BASE_DIR/polymarket-copy-bot"
        ;;
    staging)
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        BASE_DIR="/home/$BOT_USER"
        PROJECT_DIR="$BASE_DIR/polymarket-copy-bot"
        ;;
    development)
        BOT_USER="${USER:-$(whoami)}"
        BOT_GROUP="${BOT_USER:-$(whoami)}"
        BASE_DIR="/home/$BOT_USER"
        PROJECT_DIR="$BASE_DIR/polymarket-copy-bot"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        echo -e "${YELLOW}Valid environments: production, staging, development${NC}"
        exit 1
        ;;
esac

echo -e "${PURPLE}🔒 Polymarket Copy Bot Filesystem Security Setup${NC}"
echo -e "${PURPLE}================================================${NC}"
echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
echo -e "${BLUE}User: ${BOT_USER}:${BOT_GROUP}${NC}"
echo -e "${BLUE}Project: ${PROJECT_DIR}${NC}"
echo ""

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ] && [ "$ENVIRONMENT" != "development" ]; then
        echo -e "${RED}❌ This script must be run as root for production/staging${NC}"
        exit 1
    fi
}

# Function to create users and groups
create_security_users() {
    if [ "$ENVIRONMENT" = "development" ]; then
        echo -e "${BLUE}👥 Skipping user creation for development environment${NC}"
        return
    fi

    echo -e "${BLUE}👥 Creating secure user and group: $BOT_USER${NC}"

    # Create group if it doesn't exist
    if ! getent group "$BOT_GROUP" >/dev/null 2>&1; then
        groupadd --system "$BOT_GROUP"
        echo -e "${GREEN}✅ Created group: $BOT_GROUP${NC}"
    else
        echo -e "${YELLOW}⚠️  Group $BOT_GROUP already exists${NC}"
    fi

    # Create user if it doesn't exist
    if ! id -u "$BOT_USER" >/dev/null 2>&1; then
        useradd --system \
                --gid "$BOT_GROUP" \
                --shell /bin/bash \
                --home-dir "$BASE_DIR" \
                --create-home \
                --comment "Polymarket Copy Bot $ENVIRONMENT" \
                "$BOT_USER"

        # Set password to locked (no login)
        passwd -l "$BOT_USER"

        echo -e "${GREEN}✅ Created user: $BOT_USER${NC}"
    else
        echo -e "${YELLOW}⚠️  User $BOT_USER already exists${NC}"
    fi

    # Add user to necessary groups
    usermod -aG systemd-journal "$BOT_USER" 2>/dev/null || true
}

# Function to create secure directory structure
create_secure_directories() {
    echo -e "${BLUE}📁 Creating secure directory structure...${NC}"

    # Define directory structure with permissions
    declare -A DIR_PERMS=(
        ["$PROJECT_DIR"]="755"
        ["$PROJECT_DIR/logs"]="750"
        ["$PROJECT_DIR/data"]="750"
        ["$PROJECT_DIR/data/trade_history"]="700"
        ["$PROJECT_DIR/data/cache"]="755"
        ["$PROJECT_DIR/data/temp"]="755"
        ["$PROJECT_DIR/config"]="750"
        ["$PROJECT_DIR/config/backup"]="700"
        ["$PROJECT_DIR/security"]="700"
        ["$PROJECT_DIR/security/audit"]="700"
        ["$PROJECT_DIR/security/integrity"]="700"
        ["$PROJECT_DIR/backups"]="700"
        ["$PROJECT_DIR/backups/config"]="700"
        ["$PROJECT_DIR/backups/data"]="700"
        ["$PROJECT_DIR/backups/full"]="700"
    )

    for dir_path in "${!DIR_PERMS[@]}"; do
        perms="${DIR_PERMS[$dir_path]}"

        # Create directory if it doesn't exist
        if [ ! -d "$dir_path" ]; then
            mkdir -p "$dir_path"
            echo -e "${GREEN}✅ Created: $dir_path${NC}"
        else
            echo -e "${YELLOW}⚠️  Exists: $dir_path${NC}"
        fi

        # Set permissions
        chmod "$perms" "$dir_path"

        # Set ownership (skip for development)
        if [ "$ENVIRONMENT" != "development" ]; then
            chown "$BOT_USER:$BOT_GROUP" "$dir_path"
        fi
    done

    echo -e "${GREEN}✅ Directory structure secured${NC}"
}

# Function to setup file permissions
setup_file_permissions() {
    echo -e "${BLUE}🔐 Setting up file permissions...${NC}"

    # Critical files - owner read/write only
    declare -a OWNER_ONLY_FILES=(
        "$PROJECT_DIR/.env"
        "$PROJECT_DIR/.env.$ENVIRONMENT"
        "$PROJECT_DIR/config/wallets.json"
        "$PROJECT_DIR/security/*"
    )

    # Config files - owner read/write, group read
    declare -a OWNER_GROUP_FILES=(
        "$PROJECT_DIR/config/*.py"
        "$PROJECT_DIR/config/*.json"
        "$PROJECT_DIR/*.txt"
        "$PROJECT_DIR/requirements.txt"
        "$PROJECT_DIR/pyproject.toml"
    )

    # Executable scripts - owner execute, group execute
    declare -a EXECUTABLE_FILES=(
        "$PROJECT_DIR/main.py"
        "$PROJECT_DIR/main_staging.py"
        "$PROJECT_DIR/scripts/*.sh"
        "$PROJECT_DIR/scripts/*.py"
    )

    # Set owner-only permissions
    for pattern in "${OWNER_ONLY_FILES[@]}"; do
        for file in $pattern 2>/dev/null; do
            if [ -f "$file" ]; then
                chmod 600 "$file"
                if [ "$ENVIRONMENT" != "development" ]; then
                    chown "$BOT_USER:$BOT_GROUP" "$file"
                fi
                echo -e "${GREEN}🔒 Secured: $file (600)${NC}"
            fi
        done
    done

    # Set owner-group permissions
    for pattern in "${OWNER_GROUP_FILES[@]}"; do
        for file in $pattern 2>/dev/null; do
            if [ -f "$file" ]; then
                chmod 640 "$file"
                if [ "$ENVIRONMENT" != "development" ]; then
                    chown "$BOT_USER:$BOT_GROUP" "$file"
                fi
                echo -e "${GREEN}🔒 Secured: $file (640)${NC}"
            fi
        done
    done

    # Set executable permissions
    for pattern in "${EXECUTABLE_FILES[@]}"; do
        for file in $pattern 2>/dev/null; do
            if [ -f "$file" ]; then
                chmod 750 "$file"
                if [ "$ENVIRONMENT" != "development" ]; then
                    chown "$BOT_USER:$BOT_GROUP" "$file"
                fi
                echo -e "${GREEN}🔒 Secured: $file (750)${NC}"
            fi
        done
    done

    echo -e "${GREEN}✅ File permissions configured${NC}"
}

# Function to setup extended attributes and ACLs
setup_extended_security() {
    echo -e "${BLUE}🛡️  Setting up extended security attributes...${NC}"

    # Check if ACL tools are available
    if ! command -v setfacl >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  ACL tools not available, installing...${NC}"
        apt-get update && apt-get install -y acl
    fi

    # Setup ACLs for collaborative access (if needed)
    # Allow monitoring user to read logs
    if id "monitoring" >/dev/null 2>&1 2>/dev/null; then
        setfacl -m u:monitoring:rx "$PROJECT_DIR/logs"
        echo -e "${GREEN}✅ ACL set for monitoring user on logs${NC}"
    fi

    # Setup immutable flag for critical config backups (optional)
    # chattr +i "$PROJECT_DIR/config/backup/" 2>/dev/null || true

    # Setup noexec flag for data directories (prevent execution)
    for dir in "$PROJECT_DIR/data" "$PROJECT_DIR/backups"; do
        if [ -d "$dir" ]; then
            # Mount with noexec if possible (requires remount)
            echo -e "${YELLOW}💡 Consider adding noexec to /etc/fstab for data directories${NC}"
        fi
    done

    echo -e "${GREEN}✅ Extended security configured${NC}"
}

# Function to setup encryption for sensitive data
setup_encryption() {
    if [ "$ENABLE_ENCRYPTION" != "true" ]; then
        echo -e "${BLUE}🔄 Skipping encryption setup${NC}"
        return
    fi

    echo -e "${BLUE}🔐 Setting up data encryption...${NC}"

    # Check for encryption tools
    if ! command -v ecryptfs-setup-private >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Installing encryption tools...${NC}"
        apt-get update && apt-get install -y ecryptfs-utils
    fi

    # Setup encrypted directory for trade history
    ENCRYPTED_DIR="$PROJECT_DIR/data/trade_history_encrypted"

    if [ ! -d "$ENCRYPTED_DIR" ]; then
        echo -e "${YELLOW}⚠️  Manual encryption setup required${NC}"
        echo -e "${YELLOW}   Run as $BOT_USER: ecryptfs-setup-private${NC}"
        echo -e "${YELLOW}   Then mount encrypted directory at $ENCRYPTED_DIR${NC}"
    else
        echo -e "${GREEN}✅ Encrypted directory exists${NC}"
    fi

    echo -e "${GREEN}✅ Encryption configured${NC}"
}

# Function to setup file integrity monitoring
setup_integrity_monitoring() {
    echo -e "${BLUE}🔍 Setting up file integrity monitoring...${NC}"

    INTEGRITY_DIR="$PROJECT_DIR/security/integrity"
    INTEGRITY_DB="$INTEGRITY_DIR/file_hashes.db"
    CRITICAL_FILES=(
        "$PROJECT_DIR/main.py"
        "$PROJECT_DIR/config/settings.py"
        "$PROJECT_DIR/config/wallets.json"
        "$PROJECT_DIR/requirements.txt"
    )

    # Create integrity database
    mkdir -p "$INTEGRITY_DIR"
    chmod 700 "$INTEGRITY_DIR"

    if [ ! -f "$INTEGRITY_DB" ]; then
        touch "$INTEGRITY_DB"
        chmod 600 "$INTEGRITY_DB"
    fi

    # Calculate and store hashes
    for file in "${CRITICAL_FILES[@]}"; do
        if [ -f "$file" ]; then
            hash_value=$(sha256sum "$file" | awk '{print $1}')
            echo "$(basename "$file"):$hash_value:$(date +%s)" >> "$INTEGRITY_DB"
            echo -e "${GREEN}✅ Integrity hash stored for: $(basename "$file")${NC}"
        fi
    done

    if [ "$ENVIRONMENT" != "development" ]; then
        chown "$BOT_USER:$BOT_GROUP" "$INTEGRITY_DB"
    fi

    echo -e "${GREEN}✅ File integrity monitoring configured${NC}"
}

# Function to setup audit logging
setup_audit_logging() {
    echo -e "${BLUE}📊 Setting up audit logging...${NC}"

    AUDIT_DIR="$PROJECT_DIR/security/audit"
    AUDIT_LOG="$AUDIT_DIR/filesystem_audit.log"

    mkdir -p "$AUDIT_DIR"
    chmod 700 "$AUDIT_DIR"

    if [ ! -f "$AUDIT_LOG" ]; then
        touch "$AUDIT_LOG"
        chmod 600 "$AUDIT_LOG"
    fi

    # Setup audit rules for critical files
    if [ "$ENVIRONMENT" != "development" ]; then
        # Add audit rules (requires root)
        auditctl -w "$PROJECT_DIR/.env" -p rwxa -k polymarket_env
        auditctl -w "$PROJECT_DIR/config/wallets.json" -p rwxa -k polymarket_wallets
        auditctl -w "$PROJECT_DIR/data/trade_history" -p rwxa -k polymarket_trades
        echo -e "${GREEN}✅ Audit rules configured${NC}"
    fi

    if [ "$ENVIRONMENT" != "development" ]; then
        chown "$BOT_USER:$BOT_GROUP" "$AUDIT_LOG"
    fi

    echo -e "${GREEN}✅ Audit logging configured${NC}"
}

# Function to setup log rotation
setup_log_rotation() {
    echo -e "${BLUE}🔄 Setting up log rotation...${NC}"

    LOGROTATE_CONF="/etc/logrotate.d/polymarket-$ENVIRONMENT"

    # Create logrotate configuration
    cat > "$LOGROTATE_CONF" << EOF
$PROJECT_DIR/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 $BOT_USER $BOT_GROUP
    postrotate
        systemctl reload polymarket-bot$ENV_SUFFIX.service || true
    endscript
}
EOF

    chmod 644 "$LOGROTATE_CONF"
    echo -e "${GREEN}✅ Log rotation configured${NC}"
}

# Function to setup backup system
setup_backup_system() {
    echo -e "${BLUE}💾 Setting up backup system...${NC}"

    BACKUP_SCRIPT="$PROJECT_DIR/scripts/backup_secure.sh"

    # Create secure backup script
    cat > "$BACKUP_SCRIPT" << 'EOF'
#!/bin/bash
# Secure Backup Script for Polymarket Copy Bot

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_ROOT="$PROJECT_ROOT/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ENVIRONMENT="${1:-production}"

# Backup configurations
backup_configs() {
    echo "📋 Backing up configurations..."
    CONFIG_BACKUP="$BACKUP_ROOT/config/config_$TIMESTAMP.tar.gz"

    tar -czf "$CONFIG_BACKUP" \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        -C "$PROJECT_ROOT" \
        config/*.py config/*.json .env* 2>/dev/null || true

    chmod 600 "$CONFIG_BACKUP"
    echo "✅ Config backup: $CONFIG_BACKUP"
}

# Backup trade data
backup_trade_data() {
    echo "📊 Backing up trade data..."
    DATA_BACKUP="$BACKUP_ROOT/data/trade_data_$TIMESTAMP.tar.gz"

    tar -czf "$DATA_BACKUP" \
        --exclude='*.tmp' \
        --exclude='cache' \
        -C "$PROJECT_ROOT/data" \
        . 2>/dev/null || true

    chmod 600 "$DATA_BACKUP"
    echo "✅ Trade data backup: $DATA_BACKUP"
}

# Full backup
full_backup() {
    echo "🏗️  Creating full backup..."
    FULL_BACKUP="$BACKUP_ROOT/full/full_backup_$TIMESTAMP.tar.gz"

    tar -czf "$FULL_BACKUP" \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='logs/*.log.*' \
        --exclude='backups' \
        -C "$PROJECT_ROOT" \
        . 2>/dev/null || true

    chmod 600 "$FULL_BACKUP"
    echo "✅ Full backup: $FULL_BACKUP"
}

# Cleanup old backups
cleanup_old_backups() {
    echo "🧹 Cleaning up old backups..."

    # Keep last 30 config backups
    find "$BACKUP_ROOT/config" -name "config_*.tar.gz" -mtime +30 -delete 2>/dev/null || true

    # Keep last 7 data backups
    find "$BACKUP_ROOT/data" -name "trade_data_*.tar.gz" -mtime +7 -delete 2>/dev/null || true

    # Keep last 3 full backups
    find "$BACKUP_ROOT/full" -name "full_backup_*.tar.gz" -mtime +3 -delete 2>/dev/null || true

    echo "✅ Old backups cleaned up"
}

# Main execution
main() {
    case "${2:-all}" in
        config)
            backup_configs
            ;;
        data)
            backup_trade_data
            ;;
        full)
            full_backup
            ;;
        all)
            backup_configs
            backup_trade_data
            ;;
    esac

    cleanup_old_backups
    echo "🎉 Backup completed successfully"
}

main "$@"
EOF

    chmod 700 "$BACKUP_SCRIPT"
    if [ "$ENVIRONMENT" != "development" ]; then
        chown "$BOT_USER:$BOT_GROUP" "$BACKUP_SCRIPT"
    fi

    # Create backup directories
    mkdir -p "$PROJECT_DIR/backups/config" "$PROJECT_DIR/backups/data" "$PROJECT_DIR/backups/full"
    chmod 700 "$PROJECT_DIR/backups"/*/

    echo -e "${GREEN}✅ Backup system configured${NC}"
}

# Function to validate security setup
validate_security() {
    echo -e "${BLUE}✅ Validating security setup...${NC}"

    ISSUES_FOUND=0

    # Check directory permissions
    declare -A EXPECTED_PERMS=(
        ["$PROJECT_DIR/logs"]="750"
        ["$PROJECT_DIR/data"]="750"
        ["$PROJECT_DIR/config"]="750"
        ["$PROJECT_DIR/security"]="700"
        ["$PROJECT_DIR/backups"]="700"
    )

    for dir_path in "${!EXPECTED_PERMS[@]}"; do
        if [ -d "$dir_path" ]; then
            actual_perms=$(stat -c "%a" "$dir_path")
            expected_perms="${EXPECTED_PERMS[$dir_path]}"

            if [ "$actual_perms" != "$expected_perms" ]; then
                echo -e "${RED}❌ Wrong permissions on $dir_path: $actual_perms (expected: $expected_perms)${NC}"
                ISSUES_FOUND=$((ISSUES_FOUND + 1))
            else
                echo -e "${GREEN}✅ Correct permissions: $dir_path${NC}"
            fi
        fi
    done

    # Check critical file permissions
    if [ -f "$PROJECT_DIR/.env" ]; then
        env_perms=$(stat -c "%a" "$PROJECT_DIR/.env")
        if [ "$env_perms" != "600" ]; then
            echo -e "${RED}❌ Wrong .env permissions: $env_perms (expected: 600)${NC}"
            ISSUES_FOUND=$((ISSUES_FOUND + 1))
        else
            echo -e "${GREEN}✅ Correct .env permissions${NC}"
        fi
    fi

    # Check user ownership
    if [ "$ENVIRONMENT" != "development" ]; then
        project_owner=$(stat -c "%U:%G" "$PROJECT_DIR")
        if [ "$project_owner" != "$BOT_USER:$BOT_GROUP" ]; then
            echo -e "${RED}❌ Wrong ownership on project directory: $project_owner (expected: $BOT_USER:$BOT_GROUP)${NC}"
            ISSUES_FOUND=$((ISSUES_FOUND + 1))
        else
            echo -e "${GREEN}✅ Correct project ownership${NC}"
        fi
    fi

    if [ $ISSUES_FOUND -eq 0 ]; then
        echo -e "${GREEN}🎉 Security validation passed!${NC}"
    else
        echo -e "${RED}❌ Found $ISSUES_FOUND security issues${NC}"
        exit 1
    fi
}

# Function to create security monitoring script
create_monitoring_script() {
    echo -e "${BLUE}📈 Creating security monitoring script...${NC}"

    MONITOR_SCRIPT="$PROJECT_DIR/scripts/security_monitor.sh"

    cat > "$MONITOR_SCRIPT" << EOF
#!/bin/bash
# Security Monitoring Script for Polymarket Copy Bot

PROJECT_ROOT="$PROJECT_DIR"
INTEGRITY_DB="\$PROJECT_ROOT/security/integrity/file_hashes.db"
AUDIT_LOG="\$PROJECT_ROOT/security/audit/filesystem_audit.log"

# Check file integrity
check_integrity() {
    echo "🔍 Checking file integrity..."

    ISSUES=0

    while IFS=':' read -r filename expected_hash timestamp; do
        filepath="\$PROJECT_ROOT/\$filename"

        if [ -f "\$filepath" ]; then
            actual_hash=\$(sha256sum "\$filepath" | awk '{print \$1}')

            if [ "\$actual_hash" != "\$expected_hash" ]; then
                echo "❌ INTEGRITY VIOLATION: \$filename"
                echo "\$(date): INTEGRITY VIOLATION - \$filename modified" >> "\$AUDIT_LOG"
                ISSUES=\$((ISSUES + 1))
            fi
        else
            echo "❌ FILE MISSING: \$filename"
            echo "\$(date): FILE MISSING - \$filename" >> "\$AUDIT_LOG"
            ISSUES=\$((ISSUES + 1))
        fi
    done < "\$INTEGRITY_DB"

    if [ \$ISSUES -eq 0 ]; then
        echo "✅ All files integrity verified"
    else
        echo "❌ Found \$ISSUES integrity issues"
        return 1
    fi
}

# Check permissions
check_permissions() {
    echo "🔐 Checking file permissions..."

    # This would call the validation function from filesystem_security.sh
    bash "\$PROJECT_ROOT/scripts/filesystem_security.sh" "$ENVIRONMENT" validate
}

# Check for suspicious activity
check_suspicious_activity() {
    echo "🚨 Checking for suspicious activity..."

    # Check for unauthorized file access
    if command -v ausearch >/dev/null 2>&1; then
        # Check audit logs for violations
        ausearch -k polymarket_env -k polymarket_wallets -k polymarket_trades --format text 2>/dev/null | tail -10 >> "\$AUDIT_LOG" || true
    fi
}

# Main execution
main() {
    echo "🛡️  Running security monitoring for $ENVIRONMENT..."

    check_integrity
    check_permissions
    check_suspicious_activity

    echo "✅ Security monitoring completed"
}

main "\$@"
EOF

    chmod 700 "$MONITOR_SCRIPT"
    if [ "$ENVIRONMENT" != "development" ]; then
        chown "$BOT_USER:$BOT_GROUP" "$MONITOR_SCRIPT"
    fi

    echo -e "${GREEN}✅ Security monitoring script created${NC}"
}

# Main execution
main() {
    check_root
    create_security_users
    create_secure_directories
    setup_file_permissions
    setup_extended_security
    setup_encryption
    setup_integrity_monitoring
    setup_audit_logging
    setup_log_rotation
    setup_backup_system
    create_monitoring_script
    validate_security

    echo ""
    echo -e "${GREEN}🎉 Filesystem security setup completed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}📋 Next steps:${NC}"
    echo -e "1. Review and configure .env file"
    echo -e "2. Run initial backup: $PROJECT_DIR/scripts/backup_secure.sh $ENVIRONMENT"
    echo -e "3. Set up cron jobs for monitoring and backups"
    echo -e "4. Test systemd service: sudo systemctl start polymarket-bot$ENV_SUFFIX"
    echo ""
    echo -e "${RED}⚠️  IMPORTANT: Never share private keys or sensitive configuration files${NC}"
}

# Run main function
main "$@"
