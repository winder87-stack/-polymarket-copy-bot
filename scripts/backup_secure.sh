#!/bin/bash
# Secure Backup Script for Polymarket Copy Bot
# Implements encrypted, integrity-checked backups

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
BACKUP_TYPE="${2:-all}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_ROOT="$PROJECT_ROOT/backups"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        ENCRYPTION_ENABLED=true
        ;;
    staging)
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        ENCRYPTION_ENABLED=false
        ;;
    development)
        BOT_USER="${USER:-$(whoami)}"
        BOT_GROUP="${BOT_USER:-$(whoami)}"
        ENCRYPTION_ENABLED=false
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Function to log backup operations
log_backup() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_file="$PROJECT_ROOT/logs/backup_$ENVIRONMENT.log"

    echo "[$timestamp] [$level] $message" >> "$log_file"

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

# Function to create backup directories
create_backup_dirs() {
    log_backup "INFO" "Creating backup directories..."

    mkdir -p "$BACKUP_ROOT/config"
    mkdir -p "$BACKUP_ROOT/data"
    mkdir -p "$BACKUP_ROOT/full"
    mkdir -p "$BACKUP_ROOT/temp"

    # Set secure permissions
    chmod 700 "$BACKUP_ROOT"
    chmod 700 "$BACKUP_ROOT"/*/

    if [ "$ENVIRONMENT" != "development" ]; then
        chown -R "$BOT_USER:$BOT_GROUP" "$BACKUP_ROOT"
    fi

    log_backup "SUCCESS" "Backup directories created and secured"
}

# Function to validate backup prerequisites
validate_prerequisites() {
    log_backup "INFO" "Validating backup prerequisites..."

    # Check available disk space (need at least 2GB free)
    local available_kb=$(df "$BACKUP_ROOT" | tail -1 | awk '{print $4}')
    local available_gb=$((available_kb / 1024 / 1024))

    if [ $available_gb -lt 2 ]; then
        log_backup "ERROR" "Insufficient disk space: ${available_gb}GB available (need 2GB+)"
        return 1
    fi

    log_backup "SUCCESS" "Prerequisites validated: ${available_gb}GB available"

    # Check for required tools
    local required_tools=("tar" "gzip" "sha256sum")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            log_backup "ERROR" "Required tool not found: $tool"
            return 1
        fi
    done

    log_backup "SUCCESS" "All required tools available"
}

# Function to backup configurations
backup_configs() {
    log_backup "INFO" "Backing up configurations..."

    local config_backup="$BACKUP_ROOT/config/config_${ENVIRONMENT}_$TIMESTAMP.tar.gz"
    local temp_dir="$BACKUP_ROOT/temp/config_$TIMESTAMP"

    mkdir -p "$temp_dir"

    # Collect configuration files
    local config_files=(
        "config/settings.py"
        "config/wallets.json"
        ".env.${ENVIRONMENT}"
        "pyproject.toml"
        "requirements.txt"
        "requirements/requirements-${ENVIRONMENT}.txt"
        "systemd/polymarket-bot*.service"
    )

    for file in "${config_files[@]}"; do
        if [ -f "$PROJECT_ROOT/$file" ]; then
            mkdir -p "$temp_dir/$(dirname "$file")"
            cp "$PROJECT_ROOT/$file" "$temp_dir/$file"
        fi
    done

    # Create compressed archive
    if tar -czf "$config_backup" -C "$temp_dir" . 2>/dev/null; then
        # Set secure permissions
        chmod 600 "$config_backup"

        # Calculate and store hash
        local hash_file="${config_backup}.sha256"
        sha256sum "$config_backup" > "$hash_file"
        chmod 600 "$hash_file"

        # Get backup size
        local size=$(du -h "$config_backup" | awk '{print $1}')
        log_backup "SUCCESS" "Configuration backup created: $config_backup ($size)"

        # Cleanup temp directory
        rm -rf "$temp_dir"
    else
        log_backup "ERROR" "Failed to create configuration backup"
        rm -rf "$temp_dir"
        return 1
    fi
}

# Function to backup trade data
backup_trade_data() {
    log_backup "INFO" "Backing up trade data..."

    local data_backup="$BACKUP_ROOT/data/trade_data_${ENVIRONMENT}_$TIMESTAMP.tar.gz"
    local temp_dir="$BACKUP_ROOT/temp/trade_data_$TIMESTAMP"

    mkdir -p "$temp_dir"

    # Collect trade data files
    local data_files=(
        "data/trade_history/*.json"
        "data/trade_history/*.db"
        "logs/trade_*.log"
    )

    local files_found=false
    for pattern in "${data_files[@]}"; do
        if compgen -G "$PROJECT_ROOT/$pattern" >/dev/null; then
            mkdir -p "$temp_dir/$(dirname "$pattern")"
            cp $PROJECT_ROOT/$pattern "$temp_dir/$(dirname "$pattern")/" 2>/dev/null || true
            files_found=true
        fi
    done

    if [ "$files_found" = false ]; then
        log_backup "WARNING" "No trade data files found to backup"
        rm -rf "$temp_dir"
        return 0
    fi

    # Encrypt if enabled
    if [ "$ENCRYPTION_ENABLED" = true ] && command -v gpg >/dev/null 2>&1; then
        log_backup "INFO" "Encrypting trade data backup..."

        # Create encrypted archive
        if tar -czf - -C "$temp_dir" . | gpg --encrypt --recipient "$BOT_USER" > "${data_backup}.gpg" 2>/dev/null; then
            data_backup="${data_backup}.gpg"
            log_backup "SUCCESS" "Trade data encrypted and backed up"
        else
            log_backup "WARNING" "Encryption failed, creating unencrypted backup"
            tar -czf "$data_backup" -C "$temp_dir" . 2>/dev/null || {
                log_backup "ERROR" "Failed to create trade data backup"
                rm -rf "$temp_dir"
                return 1
            }
        fi
    else
        # Create unencrypted archive
        tar -czf "$data_backup" -C "$temp_dir" . 2>/dev/null || {
            log_backup "ERROR" "Failed to create trade data backup"
            rm -rf "$temp_dir"
            return 1
        }
    fi

    # Set secure permissions
    chmod 600 "$data_backup"

    # Calculate and store hash
    local hash_file="${data_backup}.sha256"
    sha256sum "$data_backup" > "$hash_file"
    chmod 600 "$hash_file"

    # Get backup size
    local size=$(du -h "$data_backup" | awk '{print $1}')
    log_backup "SUCCESS" "Trade data backup created: $data_backup ($size)"

    # Cleanup temp directory
    rm -rf "$temp_dir"
}

# Function to create full backup
full_backup() {
    log_backup "INFO" "Creating full backup..."

    local full_backup="$BACKUP_ROOT/full/full_backup_${ENVIRONMENT}_$TIMESTAMP.tar.gz"
    local exclude_file="$BACKUP_ROOT/temp/exclude_$TIMESTAMP.txt"

    # Create exclude file for items we don't want to backup
    cat > "$exclude_file" << EOF
venv/
__pycache__/
*.pyc
.cache/
node_modules/
*.log
backups/
logs/*.log.*.gz
.git/
.DS_Store
Thumbs.db
EOF

    # Create compressed archive with exclusions
    if tar -czf "$full_backup" \
        --exclude-from="$exclude_file" \
        --exclude-vcs \
        --exclude-backups \
        -C "$PROJECT_ROOT" \
        . 2>/dev/null; then

        # Set secure permissions
        chmod 600 "$full_backup"

        # Calculate and store hash
        local hash_file="${full_backup}.sha256"
        sha256sum "$full_backup" > "$hash_file"
        chmod 600 "$hash_file"

        # Get backup size
        local size=$(du -h "$full_backup" | awk '{print $1}')
        log_backup "SUCCESS" "Full backup created: $full_backup ($size)"

        # Cleanup exclude file
        rm -f "$exclude_file"
    else
        log_backup "ERROR" "Failed to create full backup"
        rm -f "$exclude_file"
        return 1
    fi
}

# Function to verify backup integrity
verify_backup_integrity() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        log_backup "ERROR" "Backup file not found for verification: $backup_file"
        return 1
    fi

    local hash_file="${backup_file}.sha256"

    if [ ! -f "$hash_file" ]; then
        log_backup "WARNING" "Hash file not found for backup: $backup_file"
        return 1
    fi

    if sha256sum -c "$hash_file" >/dev/null 2>&1; then
        log_backup "SUCCESS" "Backup integrity verified: $(basename "$backup_file")"
        return 0
    else
        log_backup "ERROR" "Backup integrity check FAILED: $(basename "$backup_file")"
        return 1
    fi
}

# Function to cleanup old backups
cleanup_old_backups() {
    log_backup "INFO" "Cleaning up old backups..."

    local cleaned_count=0

    # Keep last 30 config backups
    local config_backups=($(ls -t "$BACKUP_ROOT/config"/config_*.tar.gz 2>/dev/null || true))
    if [ ${#config_backups[@]} -gt 30 ]; then
        for ((i=30; i<${#config_backups[@]}; i++)); do
            rm -f "${config_backups[$i]}" "${config_backups[$i]}.sha256"
            ((cleaned_count++))
        done
    fi

    # Keep last 7 data backups
    local data_backups=($(ls -t "$BACKUP_ROOT/data"/trade_data_*.tar.gz* 2>/dev/null || true))
    if [ ${#data_backups[@]} -gt 7 ]; then
        for ((i=7; i<${#data_backups[@]}; i++)); do
            rm -f "${data_backups[$i]}" "${data_backups[$i]}.sha256"
            ((cleaned_count++))
        done
    fi

    # Keep last 3 full backups
    local full_backups=($(ls -t "$BACKUP_ROOT/full"/full_backup_*.tar.gz 2>/dev/null || true))
    if [ ${#full_backups[@]} -gt 3 ]; then
        for ((i=3; i<${#full_backups[@]}; i++)); do
            rm -f "${full_backups[$i]}" "${full_backups[$i]}.sha256"
            ((cleaned_count++))
        done
    fi

    log_backup "SUCCESS" "Cleaned up $cleaned_count old backup files"
}

# Function to generate backup report
generate_backup_report() {
    local report_file="$PROJECT_ROOT/logs/backup_report_${ENVIRONMENT}_$TIMESTAMP.txt"

    {
        echo "=========================================="
        echo "Polymarket Copy Bot Backup Report"
        echo "Environment: $ENVIRONMENT"
        echo "Timestamp: $TIMESTAMP"
        echo "=========================================="
        echo ""
        echo "BACKUP SUMMARY:"
        echo "  Type: $BACKUP_TYPE"
        echo "  Location: $BACKUP_ROOT"
        echo ""
        echo "BACKUP FILES CREATED:"
        ls -la "$BACKUP_ROOT"/*/*"$TIMESTAMP"* 2>/dev/null || echo "  No backup files found"
        echo ""
        echo "DISK USAGE:"
        df -h "$BACKUP_ROOT" | tail -1
        echo ""
        echo "BACKUP DIRECTORY CONTENTS:"
        find "$BACKUP_ROOT" -type f -name "*.tar.gz*" | wc -l | xargs echo "  Total backup files:"
        du -sh "$BACKUP_ROOT" 2>/dev/null | awk '{print "  Total backup size: " $1}'
        echo ""
        echo "=========================================="
    } > "$report_file"

    chmod 600 "$report_file"
    log_backup "SUCCESS" "Backup report generated: $report_file"
}

# Function to send backup notifications (if configured)
send_notifications() {
    # This could be extended to send email/telegram notifications
    log_backup "INFO" "Backup notifications could be sent here"
}

# Main execution
main() {
    log_backup "INFO" "Starting secure backup for environment: $ENVIRONMENT (type: $BACKUP_TYPE)"

    create_backup_dirs

    if ! validate_prerequisites; then
        log_backup "ERROR" "Backup prerequisites not met"
        exit 1
    fi

    local backup_errors=0

    # Execute requested backup type
    case "$BACKUP_TYPE" in
        config)
            backup_configs || ((backup_errors++))
            ;;
        data)
            backup_trade_data || ((backup_errors++))
            ;;
        full)
            full_backup || ((backup_errors++))
            ;;
        all)
            backup_configs || ((backup_errors++))
            backup_trade_data || ((backup_errors++))
            ;;
        *)
            log_backup "ERROR" "Invalid backup type: $BACKUP_TYPE"
            exit 1
            ;;
    esac

    # Verify backup integrity
    log_backup "INFO" "Verifying backup integrity..."
    for backup_file in "$BACKUP_ROOT"/*/*"$TIMESTAMP"*.tar.gz*; do
        if [ -f "$backup_file" ]; then
            verify_backup_integrity "$backup_file" || ((backup_errors++))
        fi
    done

    # Cleanup old backups
    cleanup_old_backups

    # Generate report
    generate_backup_report

    # Send notifications
    send_notifications

    if [ $backup_errors -eq 0 ]; then
        log_backup "SUCCESS" "Backup completed successfully"
        echo -e "${GREEN}🎉 Backup completed successfully!${NC}"
        echo -e "${BLUE}📊 Check logs for details: $PROJECT_ROOT/logs/backup_${ENVIRONMENT}.log${NC}"
    else
        log_backup "ERROR" "Backup completed with $backup_errors errors"
        echo -e "${RED}❌ Backup completed with errors. Check logs for details.${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
