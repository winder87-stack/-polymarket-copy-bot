#!/bin/bash
# Setup script for Ubuntu 24.04 - Polymarket Copy Bot
set -e

echo "🚀 Setting up Polymarket Copy Bot on Ubuntu 24.04..."
echo "==============================================="

# Check if running as root
if [ "$(id -u)" != "0" ]; then
   echo "❌ This script must be run as root" 1>&2
   exit 1
fi

# Update system
echo "🔄 Updating system packages..."
apt update
DEBIAN_FRONTEND=noninteractive apt upgrade -y

# Install dependencies
echo "📦 Installing dependencies..."
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
    systemd

# Create dedicated user if it doesn't exist
if ! id -u polymarket-bot >/dev/null 2>&1; then
    echo "👥 Creating polymarket-bot user..."
    adduser --disabled-password --gecos "" polymarket-bot
    usermod -aG sudo polymarket-bot

    # Set up SSH access if needed
    mkdir -p /home/polymarket-bot/.ssh
    chmod 700 /home/polymarket-bot/.ssh

    echo "✅ Created polymarket-bot user"
fi

# Set up project directory
PROJECT_DIR="/home/polymarket-bot/polymarket-copy-bot"
echo "📁 Setting up project directory: $PROJECT_DIR"

if [ ! -d "$PROJECT_DIR" ]; then
    mkdir -p "$PROJECT_DIR"
    chown -R polymarket-bot:polymarket-bot "$PROJECT_DIR"
    chmod 755 "$PROJECT_DIR"

    # Copy current directory contents to project directory
    echo "📋 Copying project files..."
    cp -r ./* "$PROJECT_DIR/" 2>/dev/null || true

    # Create necessary directories
    mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/data" "$PROJECT_DIR/data/trades_history"
    chown -R polymarket-bot:polymarket-bot "$PROJECT_DIR"

    echo "✅ Project directory created"
else
    echo "ℹ️ Project directory already exists. Updating files..."
    cp -r ./* "$PROJECT_DIR/" 2>/dev/null || true
    chown -R polymarket-bot:polymarket-bot "$PROJECT_DIR"
fi

# Set up virtual environment
echo "🐍 Setting up Python virtual environment..."
sudo -i -u polymarket-bot bash << EOF
cd "$PROJECT_DIR"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

echo "✅ Python dependencies installed"
EOF

# Set up permissions
echo "🔒 Setting up security permissions..."
chmod 600 "$PROJECT_DIR/.env"
chmod +x "$PROJECT_DIR/main.py"
chmod -R 750 "$PROJECT_DIR/logs"
chmod -R 750 "$PROJECT_DIR/data"

# Set up systemd service
echo "⚙️ Setting up systemd service..."
cp "$PROJECT_DIR/systemd/polymarket-bot.service" /etc/systemd/system/
systemctl daemon-reload

echo "✅ Systemd service configured"

# Test the configuration
echo "🧪 Testing configuration..."
sudo -i -u polymarket-bot bash << EOF
cd "$PROJECT_DIR"
source venv/bin/activate
python -c "from config.settings import settings; settings.validate_critical_settings()"
echo "✅ Configuration validated successfully"
EOF

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Configure your environment variables:"
echo "   sudo nano $PROJECT_DIR/.env"
echo ""
echo "2. Start the bot:"
echo "   sudo systemctl start polymarket-bot"
echo ""
echo "3. Check logs:"
echo "   journalctl -u polymarket-bot -f --since '5 minutes ago'"
echo ""
echo "4. Enable auto-start on boot:"
echo "   sudo systemctl enable polymarket-bot"
echo ""
echo "⚠️  IMPORTANT: Make sure your .env file contains valid configuration before starting!"
echo "   Especially check: PRIVATE_KEY, POLYGON_RPC_URL, and POLYGONSCAN_API_KEY"
echo ""
echo "💡 Pro tip: Start with testnet (CLOB_HOST=https://clob.polymarket.com) and small amounts!"
