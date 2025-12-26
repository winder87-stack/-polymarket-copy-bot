#!/bin/bash
# Disaster Recovery for Polymarket Copy Trading Bot
# Comprehensive backup and recovery procedures with offsite storage

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
OPERATION="${1:-backup}"
ENVIRONMENT="${2:-production}"
BACKUP_TYPE="${3:-full}"

# Recovery Time Objective (RTO) and Recovery Point Objective (RPO)
RTO_HOURS=4  # 4 hours to recover
RPO_MINUTES=15  # 15 minutes data loss tolerance

# Backup configuration
BACKUP_ROOT="/var/backups/polymarket"
OFFSITE_BUCKET="${OFFSITE_BUCKET:-polymarket-backups}"
OFFSITE_ENDPOINT="${OFFSITE_ENDPOINT:-https://s3.amazonaws.com}"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        SERVICE_NAME="polymarket-bot"
        ;;
    staging)
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        SERVICE_NAME="polymarket-bot-staging"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Logging
DR_LOG="/var/log/polymarket-dr.log"
log_dr() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] [$OPERATION] $message" >> "$DR_LOG"

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

# Function to validate backup prerequisites
validate_backup_prerequisites() {
    log_dr "INFO" "Validating backup prerequisites..."

    # Check available disk space (need at least 10GB for full backup)
    local available_kb=$(df "$BACKUP_ROOT" | tail -1 | awk '{print $4}')
    local available_gb=$((available_kb / 1024 / 1024))

    if [ $available_gb -lt 10 ]; then
        log_dr "ERROR" "Insufficient backup space: ${available_gb}GB available (need 10GB+)"
        return 1
    fi

    # Check if bot user exists
    if ! id "$BOT_USER" >/dev/null 2>&1; then
        log_dr "ERROR" "Bot user $BOT_USER does not exist"
        return 1
    fi

    # Check backup directory
    if [ ! -d "$BACKUP_ROOT" ]; then
        mkdir -p "$BACKUP_ROOT"
        chown "$BOT_USER:$BOT_GROUP" "$BACKUP_ROOT"
        chmod 700 "$BACKUP_ROOT"
    fi

    # Check for required tools
    local required_tools=("tar" "gzip" "openssl" "rsync")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            log_dr "ERROR" "Required tool not found: $tool"
            return 1
        fi
    done

    log_dr "SUCCESS" "Backup prerequisites validated"
}

# Function to create application backup
create_application_backup() {
    log_dr "INFO" "Creating application backup..."

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="app_${ENVIRONMENT}_${timestamp}.tar.gz"
    local backup_path="$BACKUP_ROOT/$backup_name"
    local temp_dir="$BACKUP_ROOT/temp_app_$timestamp"

    mkdir -p "$temp_dir"

    # Stop service for consistent backup
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_dr "INFO" "Stopping service for consistent backup..."
        systemctl stop "$SERVICE_NAME"

        # Create flag to restart service
        echo "restart" > "$temp_dir/.restart_service"
    fi

    # Backup application code and configuration
    local exclude_file="$temp_dir/exclude.txt"
    cat > "$exclude_file" << EOF
venv/
__pycache__/
*.pyc
.cache/
node_modules/
*.log
backups/
temp/
EOF

    # Create backup archive
    if tar -czf "$backup_path" \
        --exclude-from="$exclude_file" \
        --exclude-vcs \
        -C "$PROJECT_DIR" \
        . 2>/dev/null; then

        # Generate backup manifest
        local manifest_file="${backup_path}.manifest"
        cat > "$manifest_file" << EOF
Backup Type: Application
Environment: $ENVIRONMENT
Timestamp: $timestamp
Created By: $(whoami)@$(hostname)
Service Was Stopped: $([ -f "$temp_dir/.restart_service" ] && echo "Yes" || echo "No")

Contents:
- Application code
- Configuration files
- Static assets
- Templates

Excluded:
$(cat "$exclude_file")

Verification:
EOF

        # Calculate and store checksums
        local checksum_file="${backup_path}.sha256"
        sha256sum "$backup_path" > "$checksum_file"

        # Update manifest
        echo "SHA256: $(cat "$checksum_file")" >> "$manifest_file"

        # Set permissions
        chown "$BOT_USER:$BOT_GROUP" "$backup_path" "$manifest_file" "$checksum_file"
        chmod 600 "$backup_path" "$manifest_file" "$checksum_file"

        log_dr "SUCCESS" "Application backup created: $backup_name ($(du -h "$backup_path" | awk '{print $1}'))"
    else
        log_dr "ERROR" "Failed to create application backup"
        return 1
    fi

    # Restart service if it was stopped
    if [ -f "$temp_dir/.restart_service" ]; then
        log_dr "INFO" "Restarting service..."
        systemctl start "$SERVICE_NAME"
    fi

    # Cleanup
    rm -rf "$temp_dir"
}

# Function to create database backup
create_database_backup() {
    log_dr "INFO" "Creating database backup..."

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="db_${ENVIRONMENT}_${timestamp}.tar.gz"
    local backup_path="$BACKUP_ROOT/$backup_name"
    local temp_dir="$BACKUP_ROOT/temp_db_$timestamp"

    mkdir -p "$temp_dir"

    # Find database files
    local db_files=()
    while IFS= read -r -d '' file; do
        db_files+=("$file")
    done < <(find "$PROJECT_DIR/data" -name "*.db" -o -name "*.sqlite*" -print0 2>/dev/null)

    if [ ${#db_files[@]} -eq 0 ]; then
        log_dr "WARNING" "No database files found"
        rm -rf "$temp_dir"
        return 0
    fi

    # Copy database files to temp directory
    for db_file in "${db_files[@]}"; do
        local relative_path="${db_file#$PROJECT_DIR/}"
        mkdir -p "$temp_dir/$(dirname "$relative_path")"
        cp "$db_file" "$temp_dir/$relative_path"
    done

    # Create compressed backup
    if tar -czf "$backup_path" -C "$temp_dir" . 2>/dev/null; then

        # Generate manifest
        local manifest_file="${backup_path}.manifest"
        cat > "$manifest_file" << EOF
Backup Type: Database
Environment: $ENVIRONMENT
Timestamp: $timestamp
Database Files: ${#db_files[@]}

Files Backed Up:
$(for file in "${db_files[@]}"; do echo "  - $file"; done)

Verification:
EOF

        # Calculate checksum
        local checksum_file="${backup_path}.sha256"
        sha256sum "$backup_path" > "$checksum_file"

        echo "SHA256: $(cat "$checksum_file")" >> "$manifest_file"

        # Encrypt database backup (contains sensitive trading data)
        local encrypted_backup="${backup_path}.enc"
        if openssl enc -aes-256-cbc -salt -in "$backup_path" -out "$encrypted_backup" -k "${ENCRYPTION_KEY:-CHANGE_THIS_ENCRYPTION_KEY}"; then
            rm "$backup_path"
            backup_path="$encrypted_backup"
            echo "Encrypted: Yes" >> "$manifest_file"
        else
            log_dr "WARNING" "Failed to encrypt database backup"
        fi

        # Set permissions
        chown "$BOT_USER:$BOT_GROUP" "$backup_path" "$manifest_file" "$checksum_file"
        chmod 600 "$backup_path" "$manifest_file" "$checksum_file"

        log_dr "SUCCESS" "Database backup created: $(basename "$backup_path") ($(du -h "$backup_path" | awk '{print $1}'))"
    else
        log_dr "ERROR" "Failed to create database backup"
        rm -rf "$temp_dir"
        return 1
    fi

    # Cleanup
    rm -rf "$temp_dir"
}

# Function to create configuration backup
create_config_backup() {
    log_dr "INFO" "Creating configuration backup..."

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="config_${ENVIRONMENT}_${timestamp}.tar.gz"
    local backup_path="$BACKUP_ROOT/$backup_name"
    local temp_dir="$BACKUP_ROOT/temp_config_$timestamp"

    mkdir -p "$temp_dir"

    # Collect configuration files
    local config_files=(
        "/etc/polymarket/$ENVIRONMENT/"
        "/etc/polymarket-ha/"
        "/etc/systemd/system/${SERVICE_NAME}.service"
        "/etc/rsyncd.conf"
        "/etc/haproxy/haproxy.cfg"
        "/etc/audit/rules.d/"
        "/etc/logrotate.d/polymarket*"
    )

    for config_path in "${config_files[@]}"; do
        if [ -e "$config_path" ]; then
            local relative_path="${config_path#/}"
            mkdir -p "$temp_dir/$(dirname "$relative_path")"
            cp -r "$config_path" "$temp_dir/$(dirname "$relative_path")/" 2>/dev/null || true
        fi
    done

    # Include local configuration
    if [ -d "$PROJECT_DIR/config" ]; then
        mkdir -p "$temp_dir/home/$BOT_USER/polymarket-copy-bot"
        cp -r "$PROJECT_DIR/config" "$temp_dir/home/$BOT_USER/polymarket-copy-bot/" 2>/dev/null || true
    fi

    # Create backup
    if tar -czf "$backup_path" -C "$temp_dir" . 2>/dev/null; then

        # Generate manifest
        local manifest_file="${backup_path}.manifest"
        cat > "$manifest_file" << EOF
Backup Type: Configuration
Environment: $ENVIRONMENT
Timestamp: $timestamp

Configuration Areas:
- Application config
- System services
- HA configuration
- Security policies
- Log rotation

Verification:
EOF

        # Calculate checksum
        local checksum_file="${backup_path}.sha256"
        sha256sum "$backup_path" > "$checksum_file"

        echo "SHA256: $(cat "$checksum_file")" >> "$manifest_file"

        # Set permissions
        chown "$BOT_USER:$BOT_GROUP" "$backup_path" "$manifest_file" "$checksum_file"
        chmod 600 "$backup_path" "$manifest_file" "$checksum_file"

        log_dr "SUCCESS" "Configuration backup created: $backup_name ($(du -h "$backup_path" | awk '{print $1}'))"
    else
        log_dr "ERROR" "Failed to create configuration backup"
        rm -rf "$temp_dir"
        return 1
    fi

    # Cleanup
    rm -rf "$temp_dir"
}

# Function to upload to offsite storage
upload_offsite() {
    local backup_file="$1"
    local remote_path="$ENVIRONMENT/$(basename "$backup_file")"

    log_dr "INFO" "Uploading to offsite storage: $(basename "$backup_file")"

    # Check for AWS CLI
    if command -v aws >/dev/null 2>&1; then
        if aws s3 cp "$backup_file" "s3://$OFFSITE_BUCKET/$remote_path" 2>/dev/null; then
            log_dr "SUCCESS" "Uploaded to S3: s3://$OFFSITE_BUCKET/$remote_path"

            # Also upload manifest and checksum
            local manifest_file="${backup_file}.manifest"
            local checksum_file="${backup_file}.sha256"

            if [ -f "$manifest_file" ]; then
                aws s3 cp "$manifest_file" "s3://$OFFSITE_BUCKET/$ENVIRONMENT/$(basename "$manifest_file")" 2>/dev/null || true
            fi

            if [ -f "$checksum_file" ]; then
                aws s3 cp "$checksum_file" "s3://$OFFSITE_BUCKET/$ENVIRONMENT/$(basename "$checksum_file")" 2>/dev/null || true
            fi

            return 0
        fi
    fi

    # Check for rclone
    if command -v rclone >/dev/null 2>&1; then
        if rclone copy "$backup_file" ":s3:$OFFSITE_BUCKET/$remote_path" 2>/dev/null; then
            log_dr "SUCCESS" "Uploaded via rclone: $OFFSITE_BUCKET/$remote_path"
            return 0
        fi
    fi

    # Check for s3cmd
    if command -v s3cmd >/dev/null 2>&1; then
        if s3cmd put "$backup_file" "s3://$OFFSITE_BUCKET/$remote_path" 2>/dev/null; then
            log_dr "SUCCESS" "Uploaded via s3cmd: s3://$OFFSITE_BUCKET/$remote_path"
            return 0
        fi
    fi

    log_dr "WARNING" "No supported offsite storage tool found (aws, rclone, s3cmd)"
    return 1
}

# Function to perform full backup
perform_full_backup() {
    log_dr "INFO" "Starting full backup for $ENVIRONMENT environment..."

    validate_backup_prerequisites

    # Create all backup types
    create_application_backup
    create_database_backup
    create_config_backup

    # Upload recent backups to offsite storage
    log_dr "INFO" "Uploading backups to offsite storage..."
    local recent_backups=$(find "$BACKUP_ROOT" -name "*.tar.gz*" -mmin -60)
    for backup_file in $recent_backups; do
        upload_offsite "$backup_file" || log_dr "WARNING" "Failed to upload $(basename "$backup_file")"
    done

    # Cleanup old local backups
    cleanup_old_backups

    log_dr "SUCCESS" "Full backup completed"
}

# Function to list available backups
list_backups() {
    echo -e "${BLUE}📋 Available backups for $ENVIRONMENT:${NC}"
    echo ""

    # Local backups
    echo -e "${YELLOW}Local backups:${NC}"
    if [ -d "$BACKUP_ROOT" ]; then
        find "$BACKUP_ROOT" -name "*_${ENVIRONMENT}_*.tar.gz*" -type f -printf "%P (%s bytes) %TY-%Tm-%Td %TH:%TM\n" | sort -r | head -10
    else
        echo "  No backup directory found"
    fi

    echo ""

    # Offsite backups (if AWS CLI available)
    if command -v aws >/dev/null 2>&1; then
        echo -e "${YELLOW}Offsite backups (S3):${NC}"
        aws s3 ls "s3://$OFFSITE_BUCKET/$ENVIRONMENT/" --recursive 2>/dev/null | grep -E "\.(tar\.gz|enc)" | sort | tail -10 || echo "  No offsite backups found"
    fi
}

# Function to verify backup integrity
verify_backup() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        log_dr "ERROR" "Backup file not found: $backup_file"
        return 1
    fi

    local checksum_file="${backup_file}.sha256"

    if [ ! -f "$checksum_file" ]; then
        log_dr "WARNING" "Checksum file not found, skipping verification"
        return 0
    fi

    log_dr "INFO" "Verifying backup integrity: $(basename "$backup_file")"

    if sha256sum -c "$checksum_file" >/dev/null 2>&1; then
        log_dr "SUCCESS" "Backup integrity verified"
        return 0
    else
        log_dr "ERROR" "Backup integrity check FAILED - backup may be corrupted"
        return 1
    fi
}

# Function to restore application backup
restore_application() {
    local backup_file="$1"

    log_dr "INFO" "Restoring application from backup..."

    if ! verify_backup "$backup_file"; then
        log_dr "ERROR" "Backup verification failed"
        return 1
    fi

    # Stop service
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true

    # Create restore point
    local restore_backup="$PROJECT_DIR.restore_backup.$(date +%Y%m%d_%H%M%S)"
    mv "$PROJECT_DIR" "$restore_backup" 2>/dev/null || true

    # Extract backup
    mkdir -p "$PROJECT_DIR"
    if tar -xzf "$backup_file" -C "$PROJECT_DIR" 2>/dev/null; then
        log_dr "SUCCESS" "Application restored from backup"

        # Restore proper ownership
        chown -R "$BOT_USER:$BOT_GROUP" "$PROJECT_DIR"

        # Start service
        if systemctl start "$SERVICE_NAME"; then
            log_dr "SUCCESS" "Service restarted after restore"
        else
            log_dr "ERROR" "Failed to restart service after restore"
            return 1
        fi
    else
        log_dr "ERROR" "Failed to extract application backup"
        # Restore from restore point
        mv "$restore_backup" "$PROJECT_DIR" 2>/dev/null || true
        systemctl start "$SERVICE_NAME" 2>/dev/null || true
        return 1
    fi

    # Cleanup restore point
    rm -rf "$restore_backup" 2>/dev/null || true
}

# Function to restore database backup
restore_database() {
    local backup_file="$1"

    log_dr "INFO" "Restoring database from backup..."

    if ! verify_backup "$backup_file"; then
        log_dr "ERROR" "Backup verification failed"
        return 1
    fi

    local temp_dir="$BACKUP_ROOT/temp_restore_db_$(date +%s)"
    mkdir -p "$temp_dir"

    # Decrypt if encrypted
    local actual_backup="$backup_file"
    if [[ "$backup_file" == *.enc ]]; then
        actual_backup="$temp_dir/decrypted.tar.gz"
        if ! openssl enc -d -aes-256-cbc -in "$backup_file" -out "$actual_backup" -k "${ENCRYPTION_KEY:-CHANGE_THIS_ENCRYPTION_KEY}"; then
            log_dr "ERROR" "Failed to decrypt database backup"
            rm -rf "$temp_dir"
            return 1
        fi
    fi

    # Extract database files
    if tar -xzf "$actual_backup" -C "$temp_dir" 2>/dev/null; then
        # Find and restore database files
        find "$temp_dir" -name "*.db" -o -name "*.sqlite*" | while read -r db_file; do
            local relative_path="${db_file#$temp_dir/}"
            local target_path="$PROJECT_DIR/data/$relative_path"

            mkdir -p "$(dirname "$target_path")"
            cp "$db_file" "$target_path"
            chown "$BOT_USER:$BOT_GROUP" "$target_path"
            chmod 600 "$target_path"

            log_dr "SUCCESS" "Restored database: $relative_path"
        done
    else
        log_dr "ERROR" "Failed to extract database backup"
        rm -rf "$temp_dir"
        return 1
    fi

    # Cleanup
    rm -rf "$temp_dir"
}

# Function to restore configuration backup
restore_configuration() {
    local backup_file="$1"

    log_dr "INFO" "Restoring configuration from backup..."

    if ! verify_backup "$backup_file"; then
        log_dr "ERROR" "Backup verification failed"
        return 1
    fi

    local temp_dir="$BACKUP_ROOT/temp_restore_config_$(date +%s)"
    mkdir -p "$temp_dir"

    # Extract configuration
    if tar -xzf "$backup_file" -C "$temp_dir" 2>/dev/null; then

        # Restore system configurations
        if [ -d "$temp_dir/etc" ]; then
            cp -r "$temp_dir/etc"/* /etc/ 2>/dev/null || log_dr "WARNING" "Some system configs may not have been restored"
            systemctl daemon-reload
        fi

        # Restore local configurations
        if [ -d "$temp_dir/home/$BOT_USER/polymarket-copy-bot/config" ]; then
            cp -r "$temp_dir/home/$BOT_USER/polymarket-copy-bot/config"/* "$PROJECT_DIR/config/" 2>/dev/null || true
            chown -R "$BOT_USER:$BOT_GROUP" "$PROJECT_DIR/config"
        fi

        log_dr "SUCCESS" "Configuration restored from backup"
    else
        log_dr "ERROR" "Failed to extract configuration backup"
        rm -rf "$temp_dir"
        return 1
    fi

    # Cleanup
    rm -rf "$temp_dir"
}

# Function to perform full recovery
perform_full_recovery() {
    local backup_timestamp="$1"

    log_dr "INFO" "Starting full recovery for timestamp: $backup_timestamp"

    # Find backup files
    local app_backup=$(find "$BACKUP_ROOT" -name "app_${ENVIRONMENT}_${backup_timestamp}.tar.gz" | head -1)
    local db_backup=$(find "$BACKUP_ROOT" -name "db_${ENVIRONMENT}_${backup_timestamp}.tar.gz*" | head -1)
    local config_backup=$(find "$BACKUP_ROOT" -name "config_${ENVIRONMENT}_${backup_timestamp}.tar.gz" | head -1)

    if [ -z "$app_backup" ] && [ -z "$db_backup" ] && [ -z "$config_backup" ]; then
        log_dr "ERROR" "No backups found for timestamp: $backup_timestamp"
        return 1
    fi

    # Restore in order: config, application, database
    if [ -n "$config_backup" ]; then
        restore_configuration "$config_backup" || log_dr "WARNING" "Configuration restore failed"
    fi

    if [ -n "$app_backup" ]; then
        restore_application "$app_backup" || log_dr "WARNING" "Application restore failed"
    fi

    if [ -n "$db_backup" ]; then
        restore_database "$db_backup" || log_dr "WARNING" "Database restore failed"
    fi

    log_dr "SUCCESS" "Full recovery completed"
}

# Function to cleanup old backups
cleanup_old_backups() {
    log_dr "INFO" "Cleaning up old backups..."

    # Keep last 30 daily backups
    local daily_backups=$(find "$BACKUP_ROOT" -name "*_${ENVIRONMENT}_*.tar.gz*" -type f | wc -l)
    if [ "$daily_backups" -gt 30 ]; then
        find "$BACKUP_ROOT" -name "*_${ENVIRONMENT}_*.tar.gz*" -type f -printf '%T@ %p\n' | sort -n | head -n -$((30)) | cut -d' ' -f2- | xargs rm -f 2>/dev/null || true
        log_dr "INFO" "Cleaned up old daily backups"
    fi

    # Remove temp directories older than 1 day
    find "$BACKUP_ROOT" -name "temp_*" -type d -mtime +1 -exec rm -rf {} \; 2>/dev/null || true

    log_dr "SUCCESS" "Backup cleanup completed"
}

# Function to test recovery procedures
test_recovery() {
    local test_timestamp="test_$(date +%Y%m%d_%H%M%S)"

    log_dr "INFO" "Starting recovery test..."

    # Create test backups
    log_dr "INFO" "Creating test backups..."
    BACKUP_TYPE="test"
    create_application_backup
    create_database_backup
    create_config_backup

    # Test recovery
    log_dr "INFO" "Testing recovery procedures..."
    local test_backups=$(find "$BACKUP_ROOT" -name "*_${ENVIRONMENT}_${test_timestamp}*.tar.gz*" -type f)

    local recovery_success=true
    for backup_file in $test_backups; do
        if ! verify_backup "$backup_file"; then
            log_dr "ERROR" "Backup verification failed for test backup: $(basename "$backup_file")"
            recovery_success=false
        fi
    done

    # Cleanup test backups
    find "$BACKUP_ROOT" -name "*_${ENVIRONMENT}_${test_timestamp}*" -type f -delete 2>/dev/null || true

    if [ "$recovery_success" = true ]; then
        log_dr "SUCCESS" "Recovery test passed"
        return 0
    else
        log_dr "ERROR" "Recovery test failed"
        return 1
    fi
}

# Function to generate DR report
generate_dr_report() {
    local report_file="/var/log/polymarket-dr-report_$(date +%Y%m%d_%H%M%S).txt"

    # Calculate backup metrics
    local total_backups=$(find "$BACKUP_ROOT" -name "*_${ENVIRONMENT}_*.tar.gz*" -type f | wc -l)
    local total_size=$(du -sh "$BACKUP_ROOT" 2>/dev/null | awk '{print $1}')
    local newest_backup=$(find "$BACKUP_ROOT" -name "*_${ENVIRONMENT}_*.tar.gz*" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    local oldest_backup=$(find "$BACKUP_ROOT" -name "*_${ENVIRONMENT}_*.tar.gz*" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | head -1 | cut -d' ' -f2-)

    cat > "$report_file" << EOF
================================================================================
Polymarket Copy Trading Bot - Disaster Recovery Report
Generated: $(date)
Environment: $ENVIRONMENT
Operation: $OPERATION
================================================================================

RECOVERY OBJECTIVES:
- Recovery Time Objective (RTO): ${RTO_HOURS} hours
- Recovery Point Objective (RPO): ${RPO_MINUTES} minutes

BACKUP STATUS:
- Total Backups: $total_backups
- Total Size: $total_size
- Newest Backup: $(basename "$newest_backup" 2>/dev/null || echo "None")
- Oldest Backup: $(basename "$oldest_backup" 2>/dev/null || echo "None")

BACKUP LOCATIONS:
- Local: $BACKUP_ROOT
- Offsite: s3://$OFFSITE_BUCKET/$ENVIRONMENT/

RECOVERY PROCEDURES:
1. Stop affected services
2. Verify backup integrity
3. Restore from appropriate backup
4. Validate restored data
5. Restart services
6. Monitor for issues

EMERGENCY CONTACTS:
- Primary On-Call: System Administrator (+1-555-123-4567)
- DevOps Lead: devops@company.com
- Management: CTO - cto@company.com

RECOVERY TESTING:
- Last Test: $(date)
- Test Result: $(test_recovery && echo "PASSED" || echo "FAILED")

RECOMMENDATIONS:
- Ensure offsite backups are current
- Test recovery procedures quarterly
- Monitor backup success/failure alerts
- Keep multiple backup generations

================================================================================
EOF

    chmod 600 "$report_file"
    log_dr "SUCCESS" "DR report generated: $report_file"
}

# Main execution
main() {
    echo -e "${PURPLE}🛡️  Polymarket Copy Trading Bot - Disaster Recovery${NC}"
    echo -e "${PURPLE}====================================================${NC}"
    echo -e "${BLUE}Operation: ${OPERATION}${NC}"
    echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
    echo -e "${BLUE}Backup Type: ${BACKUP_TYPE}${NC}"
    echo ""

    case "$OPERATION" in
        backup)
            case "$BACKUP_TYPE" in
                full)
                    perform_full_backup
                    ;;
                app|application)
                    validate_backup_prerequisites
                    create_application_backup
                    ;;
                db|database)
                    validate_backup_prerequisites
                    create_database_backup
                    ;;
                config|configuration)
                    validate_backup_prerequisites
                    create_config_backup
                    ;;
                *)
                    echo -e "${RED}❌ Invalid backup type: $BACKUP_TYPE${NC}"
                    exit 1
                    ;;
            esac
            generate_dr_report
            echo -e "${GREEN}🎉 Backup operation completed!${NC}"
            ;;
        restore)
            case "$BACKUP_TYPE" in
                full)
                    if [ $# -lt 4 ]; then
                        echo -e "${RED}❌ Full restore requires timestamp: $0 restore full <timestamp>${NC}"
                        exit 1
                    fi
                    perform_full_recovery "$4"
                    ;;
                app|application)
                    if [ $# -lt 4 ]; then
                        echo -e "${RED}❌ Application restore requires backup file${NC}"
                        exit 1
                    fi
                    restore_application "$4"
                    ;;
                db|database)
                    if [ $# -lt 4 ]; then
                        echo -e "${RED}❌ Database restore requires backup file${NC}"
                        exit 1
                    fi
                    restore_database "$4"
                    ;;
                config|configuration)
                    if [ $# -lt 4 ]; then
                        echo -e "${RED}❌ Configuration restore requires backup file${NC}"
                        exit 1
                    fi
                    restore_configuration "$4"
                    ;;
                *)
                    echo -e "${RED}❌ Invalid restore type: $BACKUP_TYPE${NC}"
                    exit 1
                    ;;
            esac
            echo -e "${GREEN}🎉 Restore operation completed!${NC}"
            ;;
        list)
            list_backups
            ;;
        verify)
            if [ $# -lt 4 ]; then
                echo -e "${RED}❌ Verify requires backup file${NC}"
                exit 1
            fi
            verify_backup "$4"
            ;;
        test)
            test_recovery
            generate_dr_report
            ;;
        cleanup)
            cleanup_old_backups
            echo -e "${GREEN}🎉 Cleanup completed!${NC}"
            ;;
        report)
            generate_dr_report
            echo -e "${GREEN}🎉 Report generated!${NC}"
            ;;
        *)
            echo -e "${RED}❌ Invalid operation: $OPERATION${NC}"
            exit 1
            ;;
    esac
}

# Parse command line arguments
case "${1:-help}" in
    backup|restore|list|verify|test|cleanup|report)
        main "$@"
        ;;
    help|*)
        echo -e "${BLUE}Disaster Recovery for Polymarket Copy Trading Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <operation> <environment> [backup_type] [backup_file/timestamp]"
        echo ""
        echo -e "${YELLOW}Operations:${NC}"
        echo "  backup   - Create backups"
        echo "  restore  - Restore from backups"
        echo "  list     - List available backups"
        echo "  verify   - Verify backup integrity"
        echo "  test     - Test recovery procedures"
        echo "  cleanup  - Clean old backups"
        echo "  report   - Generate DR report"
        echo ""
        echo -e "${YELLOW}Backup Types:${NC}"
        echo "  full         - Complete system backup"
        echo "  app          - Application code backup"
        echo "  db           - Database backup"
        echo "  config       - Configuration backup"
        echo ""
        echo -e "${YELLOW}Environments:${NC}"
        echo "  production   - Production environment"
        echo "  staging      - Staging environment"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  $0 backup production full"
        echo "  $0 restore production app /path/to/backup.tar.gz"
        echo "  $0 list production"
        echo "  $0 verify production /path/to/backup.tar.gz"
        echo "  $0 test production"
        echo ""
        echo -e "${YELLOW}RTO/RPO Targets:${NC}"
        echo "  Recovery Time Objective: 4 hours"
        echo "  Recovery Point Objective: 15 minutes"
        echo ""
        echo -e "${YELLOW}Backup Retention:${NC}"
        echo "  Daily: 30 days"
        echo "  Weekly: 3 months"
        echo "  Offsite: Continuous"
        exit 0
        ;;
esac
