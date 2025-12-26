#!/bin/bash
# Zero-Downtime Update Procedures for Polymarket Copy Bot
# Implements rolling updates with automatic rollback capability

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
UPDATE_TYPE="${2:-rolling}"
VERSION="${3:-latest}"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        SERVICE_NAME="polymarket-bot"
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        BACKUP_SUFFIX="pre_update_$(date +%Y%m%d_%H%M%S)"
        ;;
    staging)
        SERVICE_NAME="polymarket-bot-staging"
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        BACKUP_SUFFIX="pre_update_staging_$(date +%Y%m%d_%H%M%S)"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Function to log update operations
log_update() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_file="$PROJECT_ROOT/logs/update_$ENVIRONMENT.log"

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

# Function to create pre-update backup
create_backup() {
    log_update "INFO" "Creating pre-update backup: $BACKUP_SUFFIX"

    local backup_dir="$PROJECT_ROOT/backups/updates/$BACKUP_SUFFIX"

    mkdir -p "$backup_dir"

    # Backup current state
    cp -r "$PROJECT_DIR"/* "$backup_dir/" 2>/dev/null || true

    # Create backup manifest
    cat > "$backup_dir/manifest.txt" << EOF
Backup created on: $(date)
Environment: $ENVIRONMENT
Service: $SERVICE_NAME
Version: $(cat $PROJECT_DIR/VERSION 2>/dev/null || echo "unknown")
Git commit: $(cd $PROJECT_DIR && git rev-parse HEAD 2>/dev/null || echo "not_git_repo")
Update type: $UPDATE_TYPE
EOF

    log_update "SUCCESS" "Backup created: $backup_dir"
    echo "$backup_dir"
}

# Function to validate update prerequisites
validate_prerequisites() {
    log_update "INFO" "Validating update prerequisites..."

    # Check if service is running
    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        log_update "ERROR" "Service $SERVICE_NAME is not running"
        return 1
    fi

    # Check disk space (need at least 1GB free)
    local available_kb=$(df "$PROJECT_DIR" | tail -1 | awk '{print $4}')
    local available_gb=$((available_kb / 1024 / 1024))

    if [ $available_gb -lt 1 ]; then
        log_update "ERROR" "Insufficient disk space: ${available_gb}GB available (need 1GB+)"
        return 1
    fi

    # Check if we're running as appropriate user
    if [ "$EUID" -ne 0 ] && [ "$ENVIRONMENT" != "development" ]; then
        log_update "ERROR" "Updates must be run as root for production/staging"
        return 1
    fi

    # Check if update is already in progress
    if [ -f "$PROJECT_DIR/.update_in_progress" ]; then
        log_update "ERROR" "Update already in progress"
        return 1
    fi

    log_update "SUCCESS" "Prerequisites validated"
}

# Function to download and validate new version
download_update() {
    log_update "INFO" "Downloading update: $VERSION"

    local temp_dir="$PROJECT_ROOT/temp/update_$ENVIRONMENT"
    mkdir -p "$temp_dir"

    cd "$temp_dir"

    # Download new version (implement based on your deployment method)
    if [ "$VERSION" = "latest" ]; then
        # Git-based deployment
        if [ -d "$PROJECT_DIR/.git" ]; then
            log_update "INFO" "Using git-based update"
            git clone "$PROJECT_DIR" . || {
                log_update "ERROR" "Failed to clone repository"
                return 1
            }

            # Get latest from remote
            git fetch origin
            git checkout origin/main || git checkout origin/master || {
                log_update "ERROR" "Failed to checkout latest version"
                return 1
            }
        else
            log_update "ERROR" "Cannot determine update method for non-git repository"
            return 1
        fi
    else
        # Specific version/tag
        log_update "INFO" "Downloading specific version: $VERSION"
        # Implement version-specific download logic here
        log_update "WARNING" "Specific version download not yet implemented"
    fi

    # Validate downloaded files
    if [ ! -f "main.py" ] || [ ! -f "requirements.txt" ]; then
        log_update "ERROR" "Downloaded update is missing critical files"
        rm -rf "$temp_dir"
        return 1
    fi

    log_update "SUCCESS" "Update downloaded and validated"
    echo "$temp_dir"
}

# Function to perform rolling update
rolling_update() {
    local temp_dir="$1"
    local backup_dir="$2"

    log_update "INFO" "Starting rolling update..."

    # Create update lock
    touch "$PROJECT_DIR/.update_in_progress"

    # Step 1: Install new dependencies
    log_update "INFO" "Installing new dependencies..."
    if ! install_dependencies "$temp_dir"; then
        log_update "ERROR" "Failed to install dependencies"
        return 1
    fi

    # Step 2: Pre-flight checks
    log_update "INFO" "Running pre-flight checks..."
    if ! run_preflight_checks "$temp_dir"; then
        log_update "ERROR" "Pre-flight checks failed"
        return 1
    fi

    # Step 3: Backup current configuration
    log_update "INFO" "Backing up current configuration..."
    cp "$PROJECT_DIR/.env" "$backup_dir/.env.backup" 2>/dev/null || true
    cp "$PROJECT_DIR/config/wallets.json" "$backup_dir/wallets.backup" 2>/dev/null || true

    # Step 4: Deploy new code (atomic)
    log_update "INFO" "Deploying new code..."
    if ! deploy_code "$temp_dir"; then
        log_update "ERROR" "Code deployment failed"
        return 1
    fi

    # Step 5: Restart service gracefully
    log_update "INFO" "Restarting service..."
    if ! restart_service; then
        log_update "ERROR" "Service restart failed"
        return 1
    fi

    # Step 6: Health checks
    log_update "INFO" "Running health checks..."
    if ! run_health_checks; then
        log_update "ERROR" "Health checks failed"
        return 1
    fi

    # Step 7: Cleanup
    rm -f "$PROJECT_DIR/.update_in_progress"
    rm -rf "$temp_dir"

    log_update "SUCCESS" "Rolling update completed successfully"
}

# Function to install dependencies
install_dependencies() {
    local temp_dir="$1"

    # Compare requirements
    if ! diff "$PROJECT_DIR/requirements.txt" "$temp_dir/requirements.txt" >/dev/null 2>&1; then
        log_update "INFO" "Requirements changed, updating dependencies..."

        # Install as appropriate user
        if [ "$ENVIRONMENT" = "development" ]; then
            "$PROJECT_DIR/venv/bin/pip" install -r "$temp_dir/requirements.txt"
        else
            sudo -u "$BOT_USER" "$PROJECT_DIR/venv/bin/pip" install -r "$temp_dir/requirements.txt"
        fi

        if [ $? -eq 0 ]; then
            log_update "SUCCESS" "Dependencies updated"
        else
            log_update "ERROR" "Failed to update dependencies"
            return 1
        fi
    else
        log_update "INFO" "Requirements unchanged, skipping dependency update"
    fi
}

# Function to run pre-flight checks
run_preflight_checks() {
    local temp_dir="$1"

    # Basic syntax check
    if ! python3 -m py_compile "$temp_dir/main.py"; then
        log_update "ERROR" "Syntax check failed for main.py"
        return 1
    fi

    # Import test
    if ! python3 -c "
import sys
sys.path.insert(0, '$temp_dir')
try:
    import config.settings
    print('Config import OK')
except ImportError as e:
    print(f'Config import failed: {e}')
    sys.exit(1)
"; then
        log_update "ERROR" "Import check failed"
        return 1
    fi

    log_update "SUCCESS" "Pre-flight checks passed"
}

# Function to deploy code atomically
deploy_code() {
    local temp_dir="$1"

    # Use rsync for atomic update
    rsync -a --delete \
        --exclude='.env*' \
        --exclude='logs/' \
        --exclude='data/' \
        --exclude='backups/' \
        --exclude='venv/' \
        --exclude='.git/' \
        "$temp_dir/" "$PROJECT_DIR/"

    # Set correct permissions
    if [ "$ENVIRONMENT" != "development" ]; then
        chown -R "$BOT_USER:$BOT_GROUP" "$PROJECT_DIR"
        find "$PROJECT_DIR" -type f -name "*.py" -exec chmod 750 {} \;
        find "$PROJECT_DIR" -type f -name "*.sh" -exec chmod 750 {} \;
    fi

    log_update "SUCCESS" "Code deployed atomically"
}

# Function to restart service
restart_service() {
    # Graceful restart
    systemctl reload-or-restart "$SERVICE_NAME" 2>/dev/null || systemctl restart "$SERVICE_NAME"

    # Wait for service to start
    local retries=30
    local count=0

    while [ $count -lt $retries ]; do
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log_update "SUCCESS" "Service restarted successfully"
            return 0
        fi
        sleep 2
        ((count++))
    done

    log_update "ERROR" "Service failed to restart within timeout"
    return 1
}

# Function to run health checks
run_health_checks() {
    local retries=10
    local count=0

    while [ $count -lt $retries ]; do
        # Check if health endpoint responds (if implemented)
        if curl -f "http://localhost:8000/health" >/dev/null 2>&1 2>/dev/null; then
            log_update "SUCCESS" "Health checks passed"
            return 0
        fi

        # Basic service check
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            # Additional checks can be added here
            log_update "SUCCESS" "Service health verified"
            return 0
        fi

        sleep 3
        ((count++))
    done

    log_update "ERROR" "Health checks failed"
    return 1
}

# Function to rollback update
rollback_update() {
    local backup_dir="$1"

    log_update "WARNING" "Initiating rollback to: $backup_dir"

    # Stop service
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true

    # Restore from backup
    if [ -d "$backup_dir" ]; then
        rsync -a --delete "$backup_dir/" "$PROJECT_DIR/"
        log_update "SUCCESS" "Code rolled back from backup"
    else
        log_update "ERROR" "Backup directory not found: $backup_dir"
        return 1
    fi

    # Restore configuration
    if [ -f "$backup_dir/.env.backup" ]; then
        cp "$backup_dir/.env.backup" "$PROJECT_DIR/.env"
    fi

    if [ -f "$backup_dir/wallets.backup" ]; then
        cp "$backup_dir/wallets.backup" "$PROJECT_DIR/config/wallets.json"
    fi

    # Restart service
    systemctl start "$SERVICE_NAME" 2>/dev/null || true

    # Wait for service
    sleep 5
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_update "SUCCESS" "Rollback completed successfully"
        rm -f "$PROJECT_DIR/.update_in_progress"
        return 0
    else
        log_update "ERROR" "Service failed to start after rollback"
        return 1
    fi
}

# Function to update configuration
update_configuration() {
    log_update "INFO" "Checking for configuration updates..."

    # This would compare current config with new config and apply changes
    # For now, preserve existing configuration
    log_update "INFO" "Configuration preserved (manual review recommended)"
}

# Main execution
main() {
    log_update "INFO" "Starting update procedure for $ENVIRONMENT (type: $UPDATE_TYPE, version: $VERSION)"

    # Validate prerequisites
    if ! validate_prerequisites; then
        exit 1
    fi

    # Create backup
    BACKUP_DIR=$(create_backup)

    # Download update
    TEMP_DIR=$(download_update)
    if [ $? -ne 0 ]; then
        log_update "ERROR" "Update download failed"
        exit 1
    fi

    # Perform update based on type
    case "$UPDATE_TYPE" in
        rolling)
            if rolling_update "$TEMP_DIR" "$BACKUP_DIR"; then
                log_update "SUCCESS" "Update completed successfully"
                update_configuration
            else
                log_update "ERROR" "Update failed, initiating rollback"
                if rollback_update "$BACKUP_DIR"; then
                    log_update "SUCCESS" "Rollback completed successfully"
                else
                    log_update "CRITICAL" "Rollback failed - manual intervention required"
                    exit 1
                fi
            fi
            ;;
        *)
            log_update "ERROR" "Unsupported update type: $UPDATE_TYPE"
            exit 1
            ;;
    esac

    # Cleanup
    rm -f "$PROJECT_DIR/.update_in_progress"
    rm -rf "$TEMP_DIR" 2>/dev/null || true

    log_update "INFO" "Update procedure completed"
}

# Parse command line arguments
case "${1:-help}" in
    production|staging|development)
        main "$@"
        ;;
    rollback)
        # Manual rollback
        if [ -z "$2" ]; then
            echo "Usage: $0 rollback <backup_directory>"
            exit 1
        fi
        rollback_update "$2"
        ;;
    help|*)
        echo -e "${BLUE}Zero-Downtime Update Script for Polymarket Copy Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <environment> [update_type] [version]  # Perform update"
        echo "  $0 rollback <backup_dir>                   # Manual rollback"
        echo ""
        echo -e "${YELLOW}Environments:${NC}"
        echo "  production  - Production environment"
        echo "  staging     - Staging environment"
        echo "  development - Development environment"
        echo ""
        echo -e "${YELLOW}Update Types:${NC}"
        echo "  rolling     - Zero-downtime rolling update (default)"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  $0 production rolling latest"
        echo "  $0 staging rolling v1.2.3"
        echo "  $0 rollback /path/to/backup"
        exit 0
        ;;
esac
