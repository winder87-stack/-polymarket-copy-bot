#!/bin/bash
# Setup script for Polymarket Copy Bot - STAGING ENVIRONMENT
# ===========================================
#
# This script sets up the staging environment on Ubuntu 24.04.
# The staging environment runs on Polygon Mumbai testnet with
# conservative risk parameters for validation testing.
#
# 🚨 STAGING ENVIRONMENT - TESTNET ONLY 🚨
#
# ===========================================

set -e

echo "🚀 Setting up Polymarket Copy Bot - STAGING ENVIRONMENT..."
echo "=========================================================="
echo "🚨 STAGING ENVIRONMENT - TESTNET ONLY 🚨"
echo "=========================================================="

# Check if running as root
if [ "$(id -u)" != "0" ]; then
   echo "❌ This script must be run as root" 1>&2
   exit 1
fi

# Configuration
PROJECT_DIR="/home/polymarket-staging/polymarket-copy-bot"
USER_NAME="polymarket-staging"
VENV_DIR="$PROJECT_DIR/venv"
ENV_TEMPLATE="$PROJECT_DIR/env-staging-template.txt"
ENV_FILE="$PROJECT_DIR/.env.staging"

echo "📋 Configuration:"
echo "   Project dir: $PROJECT_DIR"
echo "   User: $USER_NAME"
echo "   Environment: Staging (Testnet)"

# Update system
echo "🔄 Updating system packages..."
apt update
DEBIAN_FRONTEND=noninteractive apt upgrade -y

# Install dependencies
echo "📦 Installing system dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    build-essential \
    libssl-dev \
    libffi-dev \
    pkg-config \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    software-properties-common \
    systemd \
    jq \
    htop \
    iotop \
    sysstat

# Create dedicated staging user
if ! id -u "$USER_NAME" >/dev/null 2>&1; then
    echo "👥 Creating $USER_NAME user..."
    adduser --disabled-password --gecos "Polymarket Staging Bot" "$USER_NAME"
    usermod -aG systemd-journal "$USER_NAME"

    # Set up SSH access if needed
    mkdir -p "/home/$USER_NAME/.ssh"
    chmod 700 "/home/$USER_NAME/.ssh"

    echo "✅ Created $USER_NAME user"
fi

# Create project directory
echo "📁 Creating project directory..."
mkdir -p "$PROJECT_DIR"
chown -R "$USER_NAME:$USER_NAME" "$PROJECT_DIR"

# Clone or copy project files (assuming we're running from the project directory)
if [ -f "requirements.txt" ]; then
    echo "📋 Copying project files..."
    cp -r . "$PROJECT_DIR/"
    chown -R "$USER_NAME:$USER_NAME" "$PROJECT_DIR"
else
    echo "❌ Error: requirements.txt not found. Please run this script from the project root."
    exit 1
fi

# Set up Python virtual environment
echo "🐍 Setting up Python virtual environment..."
sudo -u "$USER_NAME" bash -c "cd '$PROJECT_DIR' && python3 -m venv '$VENV_DIR'"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
sudo -u "$USER_NAME" bash -c "cd '$PROJECT_DIR' && source '$VENV_DIR/bin/activate' && pip install --upgrade pip"
sudo -u "$USER_NAME" bash -c "cd '$PROJECT_DIR' && source '$VENV_DIR/bin/activate' && pip install -r requirements.txt"

# Set up environment variables
echo "🔐 Setting up staging environment variables..."
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_TEMPLATE" ]; then
        cp "$ENV_TEMPLATE" "$ENV_FILE"
        echo "✅ Copied environment template to $ENV_FILE"
        echo "⚠️  Please edit $ENV_FILE with your staging configuration"
        echo "   - Set STAGING_PRIVATE_KEY (testnet only!)"
        echo "   - Set STAGING_TELEGRAM_BOT_TOKEN and STAGING_TELEGRAM_CHAT_ID"
        echo "   - Review all staging-specific settings"
    else
        echo "❌ Environment template not found at $ENV_TEMPLATE"
        exit 1
    fi
else
    echo "ℹ️  Environment file already exists at $ENV_FILE"
fi

# Set restrictive file permissions
echo "🔒 Setting secure file permissions..."
chown root:root "$ENV_FILE"
chmod 600 "$ENV_FILE"

# Create logs and data directories
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/logs"
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/data"

# Set directory permissions
chown -R "$USER_NAME:$USER_NAME" "$PROJECT_DIR/logs"
chown -R "$USER_NAME:$USER_NAME" "$PROJECT_DIR/data"
chmod 750 "$PROJECT_DIR/logs"
chmod 750 "$PROJECT_DIR/data"

# Install systemd service
echo "⚙️ Installing systemd service..."
SERVICE_FILE="/etc/systemd/system/polymarket-bot-staging.service"
cp "$PROJECT_DIR/systemd/polymarket-bot-staging.service" "$SERVICE_FILE"
chmod 644 "$SERVICE_FILE"

# Reload systemd
systemctl daemon-reload

# Enable and start service (but don't start automatically)
echo "🔄 Enabling staging service..."
systemctl enable polymarket-bot-staging.service

echo ""
echo "🎉 Staging environment setup completed!"
echo "========================================"
echo ""
echo "📋 Next steps:"
echo "1. Edit $ENV_FILE with your staging configuration"
echo "2. Get testnet MATIC from: https://faucet.polygon.technology/"
echo "3. Test the configuration:"
echo "   sudo -u polymarket-staging bash"
echo "   cd $PROJECT_DIR"
echo "   source venv/bin/activate"
echo "   python config/settings_staging.py"
echo ""
echo "4. Start the staging bot:"
echo "   sudo systemctl start polymarket-bot-staging"
echo ""
echo "5. Monitor staging logs:"
echo "   sudo journalctl -u polymarket-bot-staging -f -n 100"
echo ""
echo "🚨 REMEMBER: This is STAGING - TESTNET ONLY! 🚨"
echo "🚨 NEVER use mainnet private keys or real funds! 🚨"
echo ""
echo "🔍 Validation checklist:"
echo "   - [ ] Environment variables configured"
echo "   - [ ] Testnet wallet funded with MATIC"
echo "   - [ ] Telegram alerts working"
echo "   - [ ] Service starts without errors"
echo "   - [ ] Small test trades execute successfully"
echo "   - [ ] 7-day monitoring period begins"
