#!/bin/bash
# Secure Recovery Script for Polymarket Copy Bot
# Implements verified restoration from encrypted backups

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
BACKUP_FILE="$3"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_ROOT="$PROJECT_ROOT/backups"
RECOVERY_ROOT="$PROJECT_ROOT/recovery"

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

# Function to log recovery operations
log_recovery() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_file="$PROJECT_ROOT/logs/recovery_$ENVIRONMENT.log"

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

# Function to create recovery directories
create_recovery_dirs() {
    log_recovery "INFO" "Creating recovery directories..."

    mkdir -p "$RECOVERY_ROOT"
    mkdir -p "$RECOVERY_ROOT/verify"
    mkdir -p "$RECOVERY_ROOT/temp"

    # Set secure permissions
    chmod 700 "$RECOVERY_ROOT"
    chmod 700 "$RECOVERY_ROOT"/*/

    if [ "$ENVIRONMENT" != "development" ]; then
        chown -R "$BOT_USER:$BOT_GROUP" "$RECOVERY_ROOT"
    fi

    log_recovery "SUCCESS" "Recovery directories created and secured"
}

# Function to list available backups
list_available_backups() {
    echo -e "${BLUE}📋 Available backups for $ENVIRONMENT:${NC}"
    echo ""

    # Config backups
    echo -e "${YELLOW}Configuration backups:${NC}"
    if [ -d "$BACKUP_ROOT/config" ]; then
        ls -la "$BACKUP_ROOT/config"/config_${ENVIRONMENT}_*.tar.gz 2>/dev/null | head -10 || echo "  No config backups found"
    else
        echo "  No config backup directory found"
    fi

    echo ""

    # Data backups
    echo -e "${YELLOW}Trade data backups:${NC}"
    if [ -d "$BACKUP_ROOT/data" ]; then
        ls -la "$BACKUP_ROOT/data"/trade_data_${ENVIRONMENT}_*.tar.gz* 2>/dev/null | head -10 || echo "  No data backups found"
    else
        echo "  No data backup directory found"
    fi

    echo ""

    # Full backups
    echo -e "${YELLOW}Full backups:${NC}"
    if [ -d "$BACKUP_ROOT/full" ]; then
        ls -la "$BACKUP_ROOT/full"/full_backup_${ENVIRONMENT}_*.tar.gz 2>/dev/null | head -10 || echo "  No full backups found"
    else
        echo "  No full backup directory found"
    fi
}

# Function to validate backup file
validate_backup_file() {
    local backup_file="$1"

    if [ -z "$backup_file" ]; then
        log_recovery "ERROR" "No backup file specified"
        return 1
    fi

    if [ ! -f "$backup_file" ]; then
        log_recovery "ERROR" "Backup file not found: $backup_file"
        return 1
    fi

    # Check if it's a valid backup file
    if [[ "$backup_file" != *.tar.gz* ]]; then
        log_recovery "ERROR" "Invalid backup file format: $backup_file"
        return 1
    fi

    log_recovery "SUCCESS" "Backup file validated: $(basename "$backup_file")"
    return 0
}

# Function to verify backup integrity
verify_backup_integrity() {
    local backup_file="$1"
    local hash_file="${backup_file}.sha256"

    log_recovery "INFO" "Verifying backup integrity..."

    if [ ! -f "$hash_file" ]; then
        log_recovery "WARNING" "Hash file not found for backup verification"
        log_recovery "WARNING" "Proceeding without integrity check"
        return 0
    fi

    if sha256sum -c "$hash_file" >/dev/null 2>&1; then
        log_recovery "SUCCESS" "Backup integrity verified"
        return 0
    else
        log_recovery "ERROR" "Backup integrity check FAILED"
        log_recovery "ERROR" "Backup file may be corrupted or tampered with"
        return 1
    fi
}

# Function to decrypt backup if needed
decrypt_backup() {
    local backup_file="$1"
    local decrypted_file="${backup_file%.gpg}"

    if [[ "$backup_file" != *.gpg ]]; then
        # Not encrypted
        echo "$backup_file"
        return 0
    fi

    log_recovery "INFO" "Decrypting backup file..."

    if ! command -v gpg >/dev/null 2>&1; then
        log_recovery "ERROR" "GPG not available for decryption"
        return 1
    fi

    if gpg --decrypt "$backup_file" > "$decrypted_file" 2>/dev/null; then
        log_recovery "SUCCESS" "Backup decrypted successfully"
        echo "$decrypted_file"
    else
        log_recovery "ERROR" "Failed to decrypt backup"
        return 1
    fi
}

# Function to extract backup contents
extract_backup() {
    local backup_file="$1"
    local extract_dir="$2"

    log_recovery "INFO" "Extracting backup contents..."

    mkdir -p "$extract_dir"

    if tar -tzf "$backup_file" >/dev/null 2>&1; then
        if tar -xzf "$backup_file" -C "$extract_dir" 2>/dev/null; then
            log_recovery "SUCCESS" "Backup extracted successfully"
            return 0
        else
            log_recovery "ERROR" "Failed to extract backup"
            return 1
        fi
    else
        log_recovery "ERROR" "Backup file appears to be corrupted"
        return 1
    fi
}

# Function to recover configurations
recover_configs() {
    local extract_dir="$1"

    log_recovery "INFO" "Recovering configurations..."

    # Stop services before recovery
    if [ "$ENVIRONMENT" != "development" ]; then
        log_recovery "INFO" "Stopping services for safe recovery..."
        systemctl stop "polymarket-bot${ENVIRONMENT/production/}" 2>/dev/null || true
    fi

    # Backup current configs
    local current_backup="$RECOVERY_ROOT/backup_current_$TIMESTAMP"
    mkdir -p "$current_backup"

    local config_files=(
        "$PROJECT_ROOT/config/settings.py"
        "$PROJECT_ROOT/config/wallets.json"
        "$PROJECT_ROOT/.env.$ENVIRONMENT"
        "$PROJECT_ROOT/pyproject.toml"
        "$PROJECT_ROOT/requirements.txt"
    )

    for file in "${config_files[@]}"; do
        if [ -f "$file" ]; then
            mkdir -p "$current_backup/$(dirname "${file#$PROJECT_ROOT/}")"
            cp "$file" "$current_backup/$(dirname "${file#$PROJECT_ROOT/}")/"
        fi
    done

    # Recover from backup
    local recovery_errors=0
    for file in "${config_files[@]}"; do
        local relative_path="${file#$PROJECT_ROOT/}"
        if [ -f "$extract_dir/$relative_path" ]; then
            mkdir -p "$(dirname "$file")"
            cp "$extract_dir/$relative_path" "$file"

            # Set secure permissions
            if [[ "$file" == *".env"* ]] || [[ "$file" == *"wallets.json" ]]; then
                chmod 600 "$file"
            else
                chmod 640 "$file"
            fi

            if [ "$ENVIRONMENT" != "development" ]; then
                chown "$BOT_USER:$BOT_GROUP" "$file"
            fi

            log_recovery "SUCCESS" "Recovered: $relative_path"
        else
            log_recovery "WARNING" "Not found in backup: $relative_path"
        fi
    done

    # Validate recovered configurations
    if [ "$ENVIRONMENT" != "development" ]; then
        log_recovery "INFO" "Validating recovered configurations..."
        if python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
try:
    from config.settings import settings
    settings.validate_critical_settings()
    print('VALID')
except Exception as e:
    print(f'INVALID: {e}')
    sys.exit(1)
" 2>/dev/null | grep -q "VALID"; then
            log_recovery "SUCCESS" "Recovered configurations validated"
        else
            log_recovery "ERROR" "Recovered configurations failed validation"
            ((recovery_errors++))
        fi
    fi

    return $recovery_errors
}

# Function to recover trade data
recover_trade_data() {
    local extract_dir="$1"

    log_recovery "INFO" "Recovering trade data..."

    local data_dir="$PROJECT_ROOT/data"
    local trade_history_dir="$data_dir/trade_history"

    # Create data directories
    mkdir -p "$trade_history_dir"

    # Recover trade history files
    local recovered_count=0
    local total_size=0

    if [ -d "$extract_dir/data/trade_history" ]; then
        for file in "$extract_dir"/data/trade_history/*; do
            if [ -f "$file" ]; then
                filename=$(basename "$file")
                cp "$file" "$trade_history_dir/"

                # Set secure permissions
                chmod 600 "$trade_history_dir/$filename"
                if [ "$ENVIRONMENT" != "development" ]; then
                    chown "$BOT_USER:$BOT_GROUP" "$trade_history_dir/$filename"
                fi

                size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")
                total_size=$((total_size + size))
                ((recovered_count++))
            fi
        done
    fi

    # Recover logs if they exist
    if [ -d "$extract_dir/logs" ]; then
        for file in "$extract_dir"/logs/trade_*.log; do
            if [ -f "$file" ]; then
                filename=$(basename "$file")
                cp "$file" "$PROJECT_ROOT/logs/"

                chmod 640 "$PROJECT_ROOT/logs/$filename"
                if [ "$ENVIRONMENT" != "development" ]; then
                    chown "$BOT_USER:$BOT_GROUP" "$PROJECT_ROOT/logs/$filename"
                fi

                ((recovered_count++))
            fi
        done
    fi

    total_size_mb=$((total_size / 1024 / 1024))
    log_recovery "SUCCESS" "Recovered $recovered_count files (${total_size_mb}MB)"
}

# Function to recover full backup
recover_full_backup() {
    local extract_dir="$1"

    log_recovery "INFO" "Performing full recovery..."

    # This would restore everything except venv and temp files
    # Implementation depends on backup contents
    log_recovery "WARNING" "Full recovery not yet implemented"
    log_recovery "INFO" "Use selective recovery (config/data) instead"
}

# Function to restart services
restart_services() {
    if [ "$ENVIRONMENT" = "development" ]; then
        return
    fi

    log_recovery "INFO" "Restarting services..."

    # Wait a moment for file operations to complete
    sleep 2

    if systemctl restart "polymarket-bot${ENVIRONMENT/production/}" 2>/dev/null; then
        log_recovery "SUCCESS" "Services restarted successfully"
    else
        log_recovery "WARNING" "Failed to restart services automatically"
        log_recovery "INFO" "Manual restart may be required"
    fi
}

# Function to generate recovery report
generate_recovery_report() {
    local report_file="$PROJECT_ROOT/logs/recovery_report_${ENVIRONMENT}_$TIMESTAMP.txt"

    {
        echo "=========================================="
        echo "Polymarket Copy Bot Recovery Report"
        echo "Environment: $ENVIRONMENT"
        echo "Timestamp: $TIMESTAMP"
        echo "=========================================="
        echo ""
        echo "RECOVERY SUMMARY:"
        echo "  Type: $BACKUP_TYPE"
        echo "  Backup File: ${BACKUP_FILE:-Not specified}"
        echo "  Recovery Location: $RECOVERY_ROOT"
        echo ""
        echo "SYSTEM STATUS:"
        df -h "$PROJECT_ROOT" | tail -1
        echo ""
        echo "RECOVERY VERIFICATION:"
        echo "  Check logs for detailed recovery information"
        echo ""
        echo "=========================================="
    } > "$report_file"

    chmod 600 "$report_file"
    log_recovery "SUCCESS" "Recovery report generated: $report_file"
}

# Function to cleanup temporary files
cleanup_temp_files() {
    log_recovery "INFO" "Cleaning up temporary recovery files..."

    # Remove decrypted files if they exist
    find "$RECOVERY_ROOT" -name "*.tar.gz" -not -name "*.gpg" -type f -exec rm -f {} \; 2>/dev/null || true

    # Clean old temp directories (older than 1 hour)
    find "$RECOVERY_ROOT/temp" -type d -mmin +60 -exec rm -rf {} \; 2>/dev/null || true

    log_recovery "SUCCESS" "Temporary files cleaned up"
}

# Main execution
main() {
    case "${1:-help}" in
        list)
            list_available_backups
            exit 0
            ;;
        help|*)
            echo -e "${BLUE}Secure Recovery Script for Polymarket Copy Bot${NC}"
            echo ""
            echo -e "${YELLOW}Usage:${NC}"
            echo "  $0 <environment> <backup_type> <backup_file>"
            echo "  $0 list <environment>                    # List available backups"
            echo ""
            echo -e "${YELLOW}Examples:${NC}"
            echo "  $0 production config /path/to/config_backup.tar.gz"
            echo "  $0 staging data /path/to/trade_data_backup.tar.gz"
            echo "  $0 development all /path/to/full_backup.tar.gz"
            echo "  $0 list production"
            echo ""
            echo -e "${YELLOW}Backup Types:${NC}"
            echo "  config  - Recover configurations only"
            echo "  data    - Recover trade data only"
            echo "  all     - Recover both config and data"
            exit 0
            ;;
    esac

    if [ -z "$BACKUP_FILE" ]; then
        echo -e "${RED}❌ Backup file required${NC}"
        echo -e "${YELLOW}💡 Use '$0 list $ENVIRONMENT' to see available backups${NC}"
        exit 1
    fi

    log_recovery "INFO" "Starting secure recovery for environment: $ENVIRONMENT (type: $BACKUP_TYPE)"

    create_recovery_dirs

    # Validate backup file
    if ! validate_backup_file "$BACKUP_FILE"; then
        exit 1
    fi

    # Verify backup integrity
    if ! verify_backup_integrity "$BACKUP_FILE"; then
        echo -e "${RED}❌ Backup integrity check failed. Aborting recovery.${NC}"
        exit 1
    fi

    # Decrypt if needed
    actual_backup_file=$(decrypt_backup "$BACKUP_FILE")
    if [ $? -ne 0 ]; then
        exit 1
    fi

    # Extract backup
    extract_dir="$RECOVERY_ROOT/temp/recovery_$TIMESTAMP"
    if ! extract_backup "$actual_backup_file" "$extract_dir"; then
        exit 1
    fi

    local recovery_errors=0

    # Execute recovery based on type
    case "$BACKUP_TYPE" in
        config)
            recover_configs "$extract_dir" || ((recovery_errors++))
            ;;
        data)
            recover_trade_data "$extract_dir" || ((recovery_errors++))
            ;;
        all)
            recover_configs "$extract_dir" || ((recovery_errors++))
            recover_trade_data "$extract_dir" || ((recovery_errors++))
            ;;
        *)
            log_recovery "ERROR" "Invalid recovery type: $BACKUP_TYPE"
            exit 1
            ;;
    esac

    # Restart services
    restart_services

    # Generate report
    generate_recovery_report

    # Cleanup
    cleanup_temp_files

    # Clean up decrypted file if it was temporary
    if [ "$actual_backup_file" != "$BACKUP_FILE" ] && [[ "$BACKUP_FILE" == *.gpg ]]; then
        rm -f "$actual_backup_file"
    fi

    # Clean up extract directory
    rm -rf "$extract_dir"

    if [ $recovery_errors -eq 0 ]; then
        log_recovery "SUCCESS" "Recovery completed successfully"
        echo -e "${GREEN}🎉 Recovery completed successfully!${NC}"
        echo -e "${BLUE}📊 Check logs for details: $PROJECT_ROOT/logs/recovery_${ENVIRONMENT}.log${NC}"
    else
        log_recovery "ERROR" "Recovery completed with $recovery_errors errors"
        echo -e "${RED}❌ Recovery completed with errors. Check logs for details.${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
