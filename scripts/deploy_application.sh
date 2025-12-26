#!/bin/bash
# Application Deployment Script for Polymarket Copy Trading Bot
# Idempotent deployment with configuration management and validation

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
DEPLOYMENT_TYPE="${2:-rolling}"
VERSION="${3:-latest}"
ROLLBACK="${4:-false}"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        BOT_USER="polymarket-bot"
        BOT_GROUP="polymarket-bot"
        BASE_DIR="/home/$BOT_USER"
        PROJECT_DIR="$BASE_DIR/polymarket-copy-bot"
        SERVICE_NAME="polymarket-bot"
        CONFIG_DIR="/etc/polymarket"
        LOG_DIR="/var/log/polymarket"
        DATA_DIR="/var/lib/polymarket"
        BACKUP_DIR="/var/backups/polymarket"
        ;;
    staging)
        BOT_USER="polymarket-staging"
        BOT_GROUP="polymarket-staging"
        BASE_DIR="/home/$BOT_USER"
        PROJECT_DIR="$BASE_DIR/polymarket-copy-bot"
        SERVICE_NAME="polymarket-bot-staging"
        CONFIG_DIR="/etc/polymarket-staging"
        LOG_DIR="/var/log/polymarket-staging"
        DATA_DIR="/var/lib/polymarket-staging"
        BACKUP_DIR="/var/backups/polymarket-staging"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Deployment tracking
DEPLOYMENT_ID="DEPLOY-$(date +%Y%m%d-%H%M%S)"
DEPLOYMENT_LOG="$LOG_DIR/deployment_$ENVIRONMENT.log"
DEPLOYMENT_STATUS="in_progress"

# Function to log deployment operations
log_deployment() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$DEPLOYMENT_ID] [$level] $message" >> "$DEPLOYMENT_LOG"

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

# Function to update deployment status
update_deployment_status() {
    DEPLOYMENT_STATUS="$1"
    log_deployment "INFO" "Deployment status changed to: $DEPLOYMENT_STATUS"
}

# Function to validate deployment prerequisites
validate_prerequisites() {
    log_deployment "INFO" "Validating deployment prerequisites..."

    # Check if running as appropriate user
    if [ "$EUID" -eq 0 ]; then
        # Running as root - check if bot user exists
        if ! id "$BOT_USER" >/dev/null 2>&1; then
            log_deployment "ERROR" "Bot user $BOT_USER does not exist"
            return 1
        fi
    else
        # Running as bot user
        if [ "$(whoami)" != "$BOT_USER" ]; then
            log_deployment "ERROR" "Must run as $BOT_USER or root"
            return 1
        fi
    fi

    # Check available disk space (need at least 2GB)
    local available_kb=$(df "$BASE_DIR" | tail -1 | awk '{print $4}')
    local available_gb=$((available_kb / 1024 / 1024))

    if [ $available_gb -lt 2 ]; then
        log_deployment "ERROR" "Insufficient disk space: ${available_gb}GB available (need 2GB+)"
        return 1
    fi

    # Check if service exists
    if ! systemctl list-units --type=service | grep -q "$SERVICE_NAME"; then
        log_deployment "WARNING" "Service $SERVICE_NAME not found - will create during deployment"
    fi

    # Check Python availability
    if ! command -v python3 >/dev/null 2>&1; then
        log_deployment "ERROR" "Python3 not found"
        return 1
    fi

    log_deployment "SUCCESS" "Prerequisites validation passed"
}

# Function to create deployment directories
create_directories() {
    log_deployment "INFO" "Creating deployment directories..."

    # Create directories with proper permissions
    local dirs=("$CONFIG_DIR" "$LOG_DIR" "$DATA_DIR" "$BACKUP_DIR")

    for dir_path in "${dirs[@]}"; do
        if [ ! -d "$dir_path" ]; then
            mkdir -p "$dir_path"
            log_deployment "INFO" "Created directory: $dir_path"
        fi

        # Set ownership and permissions
        chown "$BOT_USER:$BOT_GROUP" "$dir_path"
        chmod 750 "$dir_path"
    done

    # Create project directory structure
    local project_dirs=(
        "$PROJECT_DIR/logs"
        "$PROJECT_DIR/data/trade_history"
        "$PROJECT_DIR/data/cache"
        "$PROJECT_DIR/data/temp"
        "$PROJECT_DIR/security/integrity"
        "$PROJECT_DIR/security/audit"
        "$PROJECT_DIR/backups/config"
        "$PROJECT_DIR/backups/data"
        "$PROJECT_DIR/backups/full"
    )

    for dir_path in "${project_dirs[@]}"; do
        mkdir -p "$dir_path"
        chown "$BOT_USER:$BOT_GROUP" "$dir_path"
    done

    # Set specific permissions
    chmod 700 "$PROJECT_DIR/data/trade_history"
    chmod 700 "$PROJECT_DIR/security"
    chmod 700 "$PROJECT_DIR/backups"

    log_deployment "SUCCESS" "Deployment directories created and secured"
}

# Function to backup current deployment
backup_current_deployment() {
    log_deployment "INFO" "Creating pre-deployment backup..."

    local backup_name="pre_deployment_$ENVIRONMENT_$(date +%Y%m%d_%H%M%S)"
    local backup_path="$BACKUP_DIR/$backup_name"

    mkdir -p "$backup_path"

    # Backup application code
    if [ -d "$PROJECT_DIR" ]; then
        cp -r "$PROJECT_DIR"/* "$backup_path/" 2>/dev/null || true
    fi

    # Backup configuration
    if [ -f "$PROJECT_DIR/.env" ]; then
        cp "$PROJECT_DIR/.env" "$backup_path/.env.backup"
    fi

    if [ -f "$PROJECT_DIR/config/wallets.json" ]; then
        cp "$PROJECT_DIR/config/wallets.json" "$backup_path/wallets.backup"
    fi

    # Backup systemd service
    if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
        cp "/etc/systemd/system/$SERVICE_NAME.service" "$backup_path/${SERVICE_NAME}.service.backup"
    fi

    # Create backup manifest
    cat > "$backup_path/manifest.txt" << EOF
Backup created on: $(date)
Environment: $ENVIRONMENT
Deployment ID: $DEPLOYMENT_ID
Service: $SERVICE_NAME

Contents:
- Application code
- Configuration files
- Systemd service file

To restore manually:
cp $backup_path/* $PROJECT_DIR/
systemctl daemon-reload
systemctl restart $SERVICE_NAME
EOF

    # Set backup permissions
    chown -R "$BOT_USER:$BOT_GROUP" "$backup_path"
    chmod 700 "$backup_path"

    log_deployment "SUCCESS" "Pre-deployment backup created: $backup_path"
    echo "$backup_path"
}

# Function to download application code
download_application() {
    local temp_dir="$PROJECT_DIR/temp/deployment_$DEPLOYMENT_ID"

    log_deployment "INFO" "Downloading application code (version: $VERSION)..."

    mkdir -p "$temp_dir"
    cd "$temp_dir"

    # Download application code
    if [ "$VERSION" = "latest" ]; then
        # Clone from git (assuming git repository)
        if [ -d "$PROJECT_ROOT/.git" ]; then
            log_deployment "INFO" "Using git repository for deployment"

            # Copy current codebase
            cp -r "$PROJECT_ROOT"/* ./

            # Update to latest if needed
            if git status >/dev/null 2>&1; then
                git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || log_deployment "WARNING" "Could not update from git"
            fi
        else
            log_deployment "ERROR" "No git repository found and version=latest specified"
            return 1
        fi
    else
        # Specific version/tag (implement version-specific download)
        log_deployment "WARNING" "Specific version deployment not yet implemented"
        # Copy current codebase as fallback
        cp -r "$PROJECT_ROOT"/* ./
    fi

    # Validate downloaded code
    if [ ! -f "main.py" ] || [ ! -f "requirements.txt" ]; then
        log_deployment "ERROR" "Downloaded code is missing critical files"
        rm -rf "$temp_dir"
        return 1
    fi

    log_deployment "SUCCESS" "Application code downloaded and validated"
    echo "$temp_dir"
}

# Function to setup Python virtual environment
setup_virtual_environment() {
    local venv_dir="$PROJECT_DIR/venv"

    log_deployment "INFO" "Setting up Python virtual environment..."

    # Create virtual environment if it doesn't exist
    if [ ! -d "$venv_dir" ]; then
        python3 -m venv "$venv_dir"
        log_deployment "SUCCESS" "Virtual environment created"
    fi

    # Activate and upgrade pip
    source "$venv_dir/bin/activate"
    pip install --upgrade pip

    # Set ownership
    chown -R "$BOT_USER:$BOT_GROUP" "$venv_dir"

    log_deployment "SUCCESS" "Virtual environment configured"
}

# Function to install dependencies
install_dependencies() {
    local code_dir="$1"
    local venv_dir="$PROJECT_DIR/venv"

    log_deployment "INFO" "Installing Python dependencies..."

    source "$venv_dir/bin/activate"

    # Install/upgrade dependencies
    pip install -r "$code_dir/requirements.txt"

    # Verify critical packages
    local critical_packages=("web3" "pydantic" "requests" "cryptography")

    for package in "${critical_packages[@]}"; do
        if ! python -c "import $package" 2>/dev/null; then
            log_deployment "ERROR" "Critical package $package not installed"
            return 1
        fi
    done

    log_deployment "SUCCESS" "Dependencies installed and verified"
}

# Function to deploy application code
deploy_application_code() {
    local code_dir="$1"

    log_deployment "INFO" "Deploying application code..."

    # Use rsync for atomic deployment
    rsync -a --delete \
        --exclude='.git/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.env*' \
        --exclude='logs/' \
        --exclude='data/' \
        --exclude='backups/' \
        --exclude='venv/' \
        --exclude='temp/' \
        --exclude='node_modules/' \
        --exclude='.pytest_cache/' \
        "$code_dir/" "$PROJECT_DIR/"

    # Set proper permissions
    chown -R "$BOT_USER:$BOT_GROUP" "$PROJECT_DIR"

    # Set executable permissions
    find "$PROJECT_DIR" -name "*.py" -exec chmod 750 {} \;
    find "$PROJECT_DIR" -name "*.sh" -exec chmod 750 {} \;

    # Set restrictive permissions on sensitive files
    if [ -f "$PROJECT_DIR/.env" ]; then
        chmod 600 "$PROJECT_DIR/.env"
    fi

    if [ -f "$PROJECT_DIR/config/wallets.json" ]; then
        chmod 600 "$PROJECT_DIR/config/wallets.json"
    fi

    log_deployment "SUCCESS" "Application code deployed"
}

# Function to configure application
configure_application() {
    log_deployment "INFO" "Configuring application..."

    # Create .env file if it doesn't exist
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        if [ -f "$PROJECT_DIR/env-$ENVIRONMENT-template.txt" ]; then
            cp "$PROJECT_DIR/env-$ENVIRONMENT-template.txt" "$PROJECT_DIR/.env"
            log_deployment "INFO" "Created .env file from template"
        else
            log_deployment "WARNING" "No environment template found - .env file must be configured manually"
        fi
    fi

    # Validate configuration
    if [ -f "$PROJECT_DIR/.env" ]; then
        # Check for required environment variables
        local required_vars=("PRIVATE_KEY" "POLYGON_RPC_URL")

        for var in "${required_vars[@]}"; do
            if ! grep -q "^$var=" "$PROJECT_DIR/.env"; then
                log_deployment "WARNING" "Required environment variable $var not found in .env"
            fi
        done

        chmod 600 "$PROJECT_DIR/.env"
        chown "$BOT_USER:$BOT_GROUP" "$PROJECT_DIR/.env"
    fi

    # Validate wallets configuration
    if [ ! -f "$PROJECT_DIR/config/wallets.json" ]; then
        log_deployment "WARNING" "Wallets configuration not found"
    else
        # Validate JSON syntax
        if python3 -c "import json; json.load(open('$PROJECT_DIR/config/wallets.json'))" 2>/dev/null; then
            chmod 600 "$PROJECT_DIR/config/wallets.json"
            chown "$BOT_USER:$BOT_GROUP" "$PROJECT_DIR/config/wallets.json"
            log_deployment "SUCCESS" "Wallets configuration validated"
        else
            log_deployment "ERROR" "Invalid JSON in wallets configuration"
            return 1
        fi
    fi

    log_deployment "SUCCESS" "Application configuration completed"
}

# Function to create systemd service
create_systemd_service() {
    log_deployment "INFO" "Creating systemd service..."

    local service_file="/etc/systemd/system/$SERVICE_NAME.service"

    # Create service file
    cat > "$service_file" << EOF
[Unit]
Description=Polymarket Copy Trading Bot ($ENVIRONMENT)
After=network.target network-online.target
Wants=network-online.target
Requires=polymarket-dependencies.service

[Service]
Type=simple
User=$BOT_USER
Group=$BOT_GROUP
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="POLYMARKET_ENV=$ENVIRONMENT"
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/main.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5
TimeoutStartSec=300
TimeoutStopSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME
PermissionsStartOnly=true

# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWriteDirectories=$LOG_DIR $DATA_DIR
ReadOnlyDirectories=$CONFIG_DIR

[Install]
WantedBy=multi-user.target
EOF

    # Create dependency service for network and disks
    cat > "/etc/systemd/system/polymarket-dependencies.service" << EOF
[Unit]
Description=Polymarket Dependencies
Requires=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/true
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    systemctl enable "polymarket-dependencies"

    log_deployment "SUCCESS" "Systemd service created and enabled"
}

# Function to run pre-deployment tests
run_pre_deployment_tests() {
    log_deployment "INFO" "Running pre-deployment tests..."

    cd "$PROJECT_DIR"

    # Activate virtual environment
    source "venv/bin/activate"

    # Test Python imports
    if ! python -c "
import sys
import config.settings
from core.clob_client import CLOBClient
print('Python imports successful')
"; then
        log_deployment "ERROR" "Python import tests failed"
        return 1
    fi

    # Test configuration loading
    if ! python -c "
from config.settings import settings
try:
    settings.validate_critical_settings()
    print('Configuration validation successful')
except Exception as e:
    print(f'Configuration validation failed: {e}')
    sys.exit(1)
"; then
        log_deployment "ERROR" "Configuration validation failed"
        return 1
    fi

    log_deployment "SUCCESS" "Pre-deployment tests passed"
}

# Function to perform rolling deployment
rolling_deployment() {
    log_deployment "INFO" "Starting rolling deployment..."

    # Create backup
    BACKUP_PATH=$(backup_current_deployment)

    # Download application
    CODE_DIR=$(download_application)
    if [ $? -ne 0 ]; then
        update_deployment_status "failed"
        exit 1
    fi

    # Setup virtual environment
    setup_virtual_environment

    # Install dependencies
    if ! install_dependencies "$CODE_DIR"; then
        log_deployment "ERROR" "Dependency installation failed"
        update_deployment_status "failed"
        exit 1
    fi

    # Run pre-deployment tests
    if ! run_pre_deployment_tests; then
        log_deployment "ERROR" "Pre-deployment tests failed"
        update_deployment_status "failed"
        exit 1
    fi

    # Deploy application code
    if ! deploy_application_code "$CODE_DIR"; then
        log_deployment "ERROR" "Code deployment failed"
        update_deployment_status "failed"
        exit 1
    fi

    # Configure application
    if ! configure_application; then
        log_deployment "ERROR" "Application configuration failed"
        update_deployment_status "failed"
        exit 1
    fi

    # Create systemd service
    create_systemd_service

    # Start service
    if ! systemctl restart "$SERVICE_NAME"; then
        log_deployment "ERROR" "Service restart failed"
        update_deployment_status "failed"
        exit 1
    fi

    # Wait for service to be healthy
    local retries=30
    local count=0

    while [ $count -lt $retries ]; do
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            # Additional health check
            sleep 5
            if curl -f --max-time 10 "http://localhost:8000/health" >/dev/null 2>&1; then
                break
            fi
        fi
        sleep 2
        ((count++))
    done

    if [ $count -eq $retries ]; then
        log_deployment "ERROR" "Service health check failed after deployment"
        update_deployment_status "failed"
        exit 1
    fi

    # Cleanup
    rm -rf "$CODE_DIR"

    update_deployment_status "completed"
    log_deployment "SUCCESS" "Rolling deployment completed successfully"
}

# Function to rollback deployment
rollback_deployment() {
    local backup_path="$1"

    log_deployment "WARNING" "Starting deployment rollback..."

    if [ -z "$backup_path" ]; then
        log_deployment "ERROR" "No backup path provided for rollback"
        return 1
    fi

    if [ ! -d "$backup_path" ]; then
        log_deployment "ERROR" "Backup directory not found: $backup_path"
        return 1
    fi

    # Stop service
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true

    # Restore from backup
    log_deployment "INFO" "Restoring application code from backup..."
    rsync -a "$backup_path/" "$PROJECT_DIR/"

    # Restore configuration
    if [ -f "$backup_path/.env.backup" ]; then
        cp "$backup_path/.env.backup" "$PROJECT_DIR/.env"
    fi

    if [ -f "$backup_path/wallets.backup" ]; then
        cp "$backup_path/wallets.backup" "$PROJECT_DIR/config/wallets.json"
    fi

    # Restore systemd service
    if [ -f "$backup_path/${SERVICE_NAME}.service.backup" ]; then
        cp "$backup_path/${SERVICE_NAME}.service.backup" "/etc/systemd/system/$SERVICE_NAME.service"
        systemctl daemon-reload
    fi

    # Set proper permissions
    chown -R "$BOT_USER:$BOT_GROUP" "$PROJECT_DIR"
    find "$PROJECT_DIR" -name "*.py" -exec chmod 750 {} \;
    find "$PROJECT_DIR" -name "*.sh" -exec chmod 750 {} \;

    if [ -f "$PROJECT_DIR/.env" ]; then
        chmod 600 "$PROJECT_DIR/.env"
    fi

    if [ -f "$PROJECT_DIR/config/wallets.json" ]; then
        chmod 600 "$PROJECT_DIR/config/wallets.json"
    fi

    # Start service
    if systemctl start "$SERVICE_NAME"; then
        # Verify service health
        sleep 10
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log_deployment "SUCCESS" "Rollback completed successfully"
            return 0
        fi
    fi

    log_deployment "ERROR" "Rollback failed - manual intervention required"
    return 1
}

# Function to generate deployment report
generate_deployment_report() {
    local report_file="$LOG_DIR/deployment_report_$ENVIRONMENT_$DEPLOYMENT_ID.txt"

    cat > "$report_file" << EOF
================================================================================
Polymarket Copy Trading Bot - Deployment Report
Deployment ID: $DEPLOYMENT_ID
Generated: $(date)
Environment: $ENVIRONMENT
Status: $DEPLOYMENT_STATUS
================================================================================

DEPLOYMENT INFORMATION:
- Type: $DEPLOYMENT_TYPE
- Version: $VERSION
- Service: $SERVICE_NAME
- User: $BOT_USER
- Project Directory: $PROJECT_DIR

SYSTEM INFORMATION:
- OS: $(lsb_release -d | cut -f2 2>/dev/null || echo "Unknown")
- Kernel: $(uname -r)
- Python: $(python3 --version 2>&1)

DEPLOYMENT STATUS:
$(grep "$DEPLOYMENT_ID" "$DEPLOYMENT_LOG" | tail -20)

SERVICE STATUS:
$(systemctl status "$SERVICE_NAME" --no-pager -l 2>/dev/null || echo "Service not found")

HEALTH CHECKS:
$(curl -s "http://localhost:8000/health" 2>/dev/null || echo "Health endpoint not responding")

CONFIGURATION VALIDATION:
$(python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
try:
    from config.settings import settings
    settings.validate_critical_settings()
    print('✅ Configuration validation passed')
except Exception as e:
    print(f'❌ Configuration validation failed: {e}')
" 2>/dev/null || echo "Configuration check failed")

NEXT STEPS:
1. Monitor application logs: tail -f $LOG_DIR/*.log
2. Check service status: systemctl status $SERVICE_NAME
3. Verify application health: curl http://localhost:8000/health
4. Monitor for errors in the first 15 minutes
5. Run backup if deployment successful

ROLLBACK INFORMATION:
- Backup Location: $BACKUP_DIR
- To rollback manually: $0 $ENVIRONMENT rollback <backup_path>
- Service restart: systemctl restart $SERVICE_NAME

================================================================================
EOF

    chmod 600 "$report_file"
    chown "$BOT_USER:$BOT_GROUP" "$report_file"

    log_deployment "SUCCESS" "Deployment report generated: $report_file"
}

# Main execution
main() {
    echo -e "${PURPLE}🚀 Polymarket Copy Trading Bot - Application Deployment${NC}"
    echo -e "${PURPLE}=====================================================${NC}"
    echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
    echo -e "${BLUE}Deployment Type: ${DEPLOYMENT_TYPE}${NC}"
    echo -e "${BLUE}Version: ${VERSION}${NC}"
    echo -e "${BLUE}Service: ${SERVICE_NAME}${NC}"
    echo ""

    log_deployment "INFO" "Starting deployment process..."

    # Handle rollback
    if [ "$ROLLBACK" = "true" ]; then
        if [ $# -lt 5 ]; then
            echo -e "${RED}❌ Rollback requires backup path: $0 $ENVIRONMENT rollback <backup_path>${NC}"
            exit 1
        fi
        ROLLBACK_PATH="$5"
        log_deployment "INFO" "Performing rollback to: $ROLLBACK_PATH"
        if rollback_deployment "$ROLLBACK_PATH"; then
            update_deployment_status "rolled_back"
            generate_deployment_report
            echo -e "${GREEN}🎉 Rollback completed successfully!${NC}"
        else
            echo -e "${RED}❌ Rollback failed${NC}"
            exit 1
        fi
        exit 0
    fi

    # Validate prerequisites
    validate_prerequisites

    # Create directories
    create_directories

    # Perform deployment based on type
    case "$DEPLOYMENT_TYPE" in
        rolling)
            rolling_deployment
            ;;
        *)
            log_deployment "ERROR" "Unsupported deployment type: $DEPLOYMENT_TYPE"
            update_deployment_status "failed"
            exit 1
            ;;
    esac

    # Generate report
    generate_deployment_report

    echo ""
    if [ "$DEPLOYMENT_STATUS" = "completed" ]; then
        echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
        echo ""
        echo -e "${YELLOW}📋 Post-Deployment Checklist:${NC}"
        echo -e "  ✅ Monitor logs: tail -f $LOG_DIR/*.log"
        echo -e "  ✅ Check service: systemctl status $SERVICE_NAME"
        echo -e "  ✅ Verify health: curl http://localhost:8000/health"
        echo -e "  ✅ Run backup: /usr/local/bin/polymarket-backup daily"
        echo -e "  ✅ Update monitoring: Check dashboards for new metrics"
    else
        echo -e "${RED}❌ Deployment failed!${NC}"
        echo -e "${YELLOW}💡 Check deployment log: $DEPLOYMENT_LOG${NC}"
        echo -e "${YELLOW}💡 Check deployment report: $LOG_DIR/deployment_report_${ENVIRONMENT}_$DEPLOYMENT_ID.txt${NC}"
        exit 1
    fi
}

# Parse command line arguments
case "${1:-help}" in
    production|staging)
        main "$@"
        ;;
    help|*)
        echo -e "${BLUE}Application Deployment Script for Polymarket Copy Trading Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <environment> [deployment_type] [version] [rollback] [rollback_path]"
        echo ""
        echo -e "${YELLOW}Environments:${NC}"
        echo "  production  - Production environment"
        echo "  staging     - Staging environment"
        echo ""
        echo -e "${YELLOW}Deployment Types:${NC}"
        echo "  rolling     - Zero-downtime rolling deployment (default)"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  $0 production rolling latest"
        echo "  $0 staging rolling v1.2.3"
        echo "  $0 production rolling latest true /path/to/backup"
        echo ""
        echo -e "${YELLOW}Rollback:${NC}"
        echo "  To rollback: $0 <environment> rolling latest true <backup_path>"
        echo "  Find backups in: /var/backups/polymarket/"
        echo ""
        echo -e "${YELLOW}Features:${NC}"
        echo "  • Idempotent deployment (safe to re-run)"
        echo "  • Automatic backup creation"
        echo "  • Pre-deployment validation"
        echo "  • Post-deployment health checks"
        echo "  • Comprehensive logging and reporting"
        echo "  • One-command rollback capability"
        exit 0
        ;;
esac
