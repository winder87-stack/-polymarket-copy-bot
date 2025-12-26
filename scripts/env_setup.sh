#!/bin/bash
# Comprehensive Environment Setup Script for Polymarket Copy Bot
# This script creates reproducible environments across different systems

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
SKIP_VALIDATION="${3:-false}"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        VENV_PATH="$PROJECT_ROOT/venv"
        REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
        ENV_TEMPLATE="$PROJECT_ROOT/env-production-template.txt"
        ENV_FILE="$PROJECT_ROOT/.env"
        USER_NAME="polymarket-bot"
        SERVICE_NAME="polymarket-bot"
        ;;
    staging)
        VENV_PATH="$PROJECT_ROOT/environments/staging/venv"
        REQUIREMENTS_FILE="$PROJECT_ROOT/requirements/requirements-staging.txt"
        ENV_TEMPLATE="$PROJECT_ROOT/env-staging-template.txt"
        ENV_FILE="$PROJECT_ROOT/.env.staging"
        USER_NAME="polymarket-staging"
        SERVICE_NAME="polymarket-bot-staging"
        ;;
    development)
        VENV_PATH="$PROJECT_ROOT/environments/development/venv"
        REQUIREMENTS_FILE="$PROJECT_ROOT/requirements/requirements-development.txt"
        ENV_TEMPLATE="$PROJECT_ROOT/env-development-template.txt"
        ENV_FILE="$PROJECT_ROOT/.env.development"
        USER_NAME="${USER:-$(whoami)}"
        SERVICE_NAME=""
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        echo -e "${YELLOW}Valid environments: production, staging, development${NC}"
        exit 1
        ;;
esac

echo -e "${PURPLE}🚀 Polymarket Copy Bot Environment Setup${NC}"
echo -e "${PURPLE}============================================${NC}"
echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
echo -e "${BLUE}Project root: ${PROJECT_ROOT}${NC}"
echo -e "${BLUE}Virtual env: ${VENV_PATH}${NC}"
echo ""

# Function to check system requirements
check_system_requirements() {
    echo -e "${BLUE}🔍 Checking system requirements...${NC}"

    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo -e "${GREEN}✅ Linux detected${NC}"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${GREEN}✅ macOS detected${NC}"
    else
        echo -e "${RED}❌ Unsupported OS: $OSTYPE${NC}"
        exit 1
    fi

    # Check Python version
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python3 not found${NC}"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 9 ] && [ "$PYTHON_MINOR" -lt 12 ]; then
        echo -e "${GREEN}✅ Python $PYTHON_VERSION is compatible${NC}"
    else
        echo -e "${RED}❌ Python $PYTHON_VERSION is not compatible (need 3.9-3.11)${NC}"
        exit 1
    fi

    # Check pip
    if ! command -v pip3 &> /dev/null; then
        echo -e "${RED}❌ pip3 not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ pip3 available${NC}"

    # Check git
    if ! command -v git &> /dev/null; then
        echo -e "${RED}❌ git not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ git available${NC}"

    # Check if running as appropriate user for production/staging
    if [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "staging" ]; then
        if [ "$EUID" -ne 0 ]; then
            echo -e "${RED}❌ Production/staging setup must run as root${NC}"
            exit 1
        fi
        echo -e "${GREEN}✅ Running as root${NC}"
    fi
}

# Function to create dedicated user (production/staging only)
create_dedicated_user() {
    if [ "$ENVIRONMENT" = "development" ]; then
        return
    fi

    echo -e "${BLUE}👥 Setting up dedicated user: $USER_NAME${NC}"

    if ! id -u "$USER_NAME" >/dev/null 2>&1; then
        useradd --create-home --shell /bin/bash "$USER_NAME"
        echo -e "${GREEN}✅ Created user: $USER_NAME${NC}"

        # Set up SSH access if needed
        mkdir -p "/home/$USER_NAME/.ssh"
        chmod 700 "/home/$USER_NAME/.ssh"
        chown "$USER_NAME:$USER_NAME" "/home/$USER_NAME/.ssh"
    else
        echo -e "${YELLOW}⚠️  User $USER_NAME already exists${NC}"
    fi
}

# Function to setup project directories
setup_directories() {
    echo -e "${BLUE}📁 Setting up project directories...${NC}"

    # Create necessary directories
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/data"
    mkdir -p "$PROJECT_ROOT/data/trades_history"
    mkdir -p "$(dirname "$VENV_PATH")"

    # Set ownership for production/staging
    if [ "$ENVIRONMENT" != "development" ]; then
        chown -R "$USER_NAME:$USER_NAME" "$PROJECT_ROOT"
        chown -R "$USER_NAME:$USER_NAME" "$(dirname "$VENV_PATH")"
    fi

    # Set permissions
    chmod 750 "$PROJECT_ROOT/logs"
    chmod 750 "$PROJECT_ROOT/data"

    echo -e "${GREEN}✅ Project directories configured${NC}"
}

# Function to create virtual environment
create_virtual_environment() {
    echo -e "${BLUE}🐍 Creating virtual environment...${NC}"

    if [ "$FORCE_RECREATE" = "true" ] && [ -d "$VENV_PATH" ]; then
        echo -e "${YELLOW}🗑️  Removing existing virtual environment...${NC}"
        rm -rf "$VENV_PATH"
    fi

    # Create virtual environment as appropriate user
    if [ "$ENVIRONMENT" = "development" ]; then
        python3 -m venv "$VENV_PATH"
    else
        sudo -u "$USER_NAME" python3 -m venv "$VENV_PATH"
    fi

    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}❌ Failed to create virtual environment${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Virtual environment created${NC}"

    # Upgrade pip
    echo -e "${BLUE}⬆️  Upgrading pip...${NC}"
    if [ "$ENVIRONMENT" = "development" ]; then
        "$VENV_PATH/bin/pip" install --upgrade pip
    else
        sudo -u "$USER_NAME" "$VENV_PATH/bin/pip" install --upgrade pip
    fi

    echo -e "${GREEN}✅ Pip upgraded${NC}"
}

# Function to generate requirements if needed
generate_requirements() {
    echo -e "${BLUE}📋 Generating requirements files...${NC}"

    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        echo -e "${YELLOW}⚠️  Requirements file not found, generating...${NC}"

        # Activate environment and run dependency manager
        if [ "$ENVIRONMENT" = "development" ]; then
            source "$VENV_PATH/bin/activate"
            python "$PROJECT_ROOT/utils/dependency_manager.py" generate
            deactivate
        else
            sudo -u "$USER_NAME" bash -c "
                source '$VENV_PATH/bin/activate'
                cd '$PROJECT_ROOT'
                python utils/dependency_manager.py generate
                deactivate
            "
        fi

        # Copy to main requirements.txt for production
        if [ "$ENVIRONMENT" = "production" ]; then
            cp "$REQUIREMENTS_FILE" "$PROJECT_ROOT/requirements.txt"
        fi
    fi

    if [ -f "$REQUIREMENTS_FILE" ]; then
        echo -e "${GREEN}✅ Requirements file ready${NC}"
    else
        echo -e "${RED}❌ Failed to generate requirements file${NC}"
        exit 1
    fi
}

# Function to install dependencies
install_dependencies() {
    echo -e "${BLUE}📦 Installing dependencies...${NC}"

    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        echo -e "${RED}❌ Requirements file not found: $REQUIREMENTS_FILE${NC}"
        exit 1
    fi

    # Install dependencies
    if [ "$ENVIRONMENT" = "development" ]; then
        "$VENV_PATH/bin/pip" install -r "$REQUIREMENTS_FILE"
    else
        sudo -u "$USER_NAME" "$VENV_PATH/bin/pip" install -r "$REQUIREMENTS_FILE"
    fi

    echo -e "${GREEN}✅ Dependencies installed${NC}"
}

# Function to setup environment variables
setup_environment_variables() {
    echo -e "${BLUE}🔐 Setting up environment variables...${NC}"

    # Create environment file from template if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_TEMPLATE" ]; then
            cp "$ENV_TEMPLATE" "$ENV_FILE"
            echo -e "${GREEN}✅ Created environment file from template${NC}"
        else
            # Create basic environment file
            cat > "$ENV_FILE" << EOF
# Polymarket Copy Bot Environment Variables
# Environment: $ENVIRONMENT
# Generated on $(date)

# REQUIRED: Your wallet private key (NEVER share this!)
PRIVATE_KEY=your_private_key_here

# REQUIRED: Polygon RPC URL
POLYGON_RPC_URL=https://polygon-rpc.com/

# OPTIONAL: PolygonScan API Key for transaction monitoring
POLYGONSCAN_API_KEY=your_api_key_here

# OPTIONAL: Telegram notifications
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Environment settings
POLYMARKET_ENV=$ENVIRONMENT
LOG_LEVEL=INFO
EOF
            echo -e "${YELLOW}⚠️  Created basic environment file. Please configure it!${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Environment file already exists${NC}"
    fi

    # Set secure permissions
    chmod 600 "$ENV_FILE"
    if [ "$ENVIRONMENT" != "development" ]; then
        chown "$USER_NAME:$USER_NAME" "$ENV_FILE"
    fi

    echo -e "${GREEN}✅ Environment variables configured${NC}"
}

# Function to setup systemd service (production/staging only)
setup_systemd_service() {
    if [ "$ENVIRONMENT" = "development" ] || [ -z "$SERVICE_NAME" ]; then
        return
    fi

    echo -e "${BLUE}⚙️  Setting up systemd service...${NC}"

    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

    # Create systemd service file
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Polymarket Copy Bot ($ENVIRONMENT)
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$PROJECT_ROOT
Environment=PATH=$VENV_PATH/bin
ExecStart=$VENV_PATH/bin/python main.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=$PROJECT_ROOT/logs $PROJECT_ROOT/data
ProtectHome=yes

[Install]
WantedBy=multi-user.target
EOF

    chmod 644 "$SERVICE_FILE"

    # Reload systemd
    systemctl daemon-reload

    # Enable service
    systemctl enable "$SERVICE_NAME"

    echo -e "${GREEN}✅ Systemd service configured${NC}"
}

# Function to run validation
run_validation() {
    if [ "$SKIP_VALIDATION" = "true" ]; then
        echo -e "${YELLOW}⚠️  Skipping validation as requested${NC}"
        return
    fi

    echo -e "${BLUE}🔍 Running environment validation...${NC}"

    # Run validation script
    if [ "$ENVIRONMENT" = "development" ]; then
        source "$VENV_PATH/bin/activate"
        export POLYMARKET_ENV="$ENVIRONMENT"
        bash "$SCRIPT_DIR/env_validate.sh" "$ENVIRONMENT"
        deactivate
    else
        sudo -u "$USER_NAME" bash -c "
            source '$VENV_PATH/bin/activate'
            export POLYMARKET_ENV='$ENVIRONMENT'
            cd '$PROJECT_ROOT'
            bash scripts/env_validate.sh '$ENVIRONMENT'
        "
    fi
}

# Function to create activation shortcut
create_activation_shortcut() {
    echo -e "${BLUE}🔗 Creating activation shortcut...${NC}"

    SHORTCUT_FILE="$PROJECT_ROOT/activate_${ENVIRONMENT}.sh"

    cat > "$SHORTCUT_FILE" << EOF
#!/bin/bash
# Activation shortcut for $ENVIRONMENT environment
source "$SCRIPT_DIR/env_activate.sh" "$ENVIRONMENT"
EOF

    chmod +x "$SHORTCUT_FILE"

    echo -e "${GREEN}✅ Created activation shortcut: $SHORTCUT_FILE${NC}"
}

# Main execution
main() {
    echo -e "${CYAN}Starting environment setup for: $ENVIRONMENT${NC}"
    echo ""

    check_system_requirements
    create_dedicated_user
    setup_directories
    create_virtual_environment
    generate_requirements
    install_dependencies
    setup_environment_variables
    setup_systemd_service
    run_validation
    create_activation_shortcut

    echo ""
    echo -e "${GREEN}🎉 Environment setup completed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}📋 Next steps:${NC}"

    if [ "$ENVIRONMENT" = "development" ]; then
        echo -e "1. Configure your environment: nano $ENV_FILE"
        echo -e "2. Activate environment: source $SHORTCUT_FILE"
        echo -e "3. Run the bot: python main.py"
    else
        echo -e "1. Configure environment variables: sudo nano $ENV_FILE"
        echo -e "2. Start the service: sudo systemctl start $SERVICE_NAME"
        echo -e "3. Check logs: journalctl -u $SERVICE_NAME -f"
    fi

    echo ""
    echo -e "${RED}⚠️  IMPORTANT: Never commit private keys or sensitive data to version control!${NC}"

    if [ "$ENVIRONMENT" = "staging" ]; then
        echo -e "${RED}🚨 STAGING ENVIRONMENT - TESTNET ONLY! 🚨${NC}"
    fi
}

# Run main function
main "$@"
