# 🚀 Native Ubuntu 24.04 Deployment Guide
# Polymarket Copy Trading Bot

**Version:** 1.0.0
**Last Updated:** December 25, 2025
**Target OS:** Ubuntu 24.04 LTS (Noble Numbat)
**Architecture:** Native (No Containers)

---

## 📋 Table of Contents

1. [System Requirements](#-system-requirements)
2. [Prerequisites](#-prerequisites)
3. [System Preparation](#-system-preparation)
4. [Application Deployment](#-application-deployment)
5. [Configuration Setup](#-configuration-setup)
6. [Service Management](#-service-management)
7. [Monitoring Setup](#-monitoring-setup)
8. [Verification & Testing](#-verification--testing)
9. [Security Hardening](#-security-hardening)
10. [Troubleshooting](#-troubleshooting)
11. [Maintenance](#-maintenance)

---

## 🖥️ System Requirements

### Hardware Requirements

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| **CPU** | 2 cores | 4 cores | 8+ cores |
| **RAM** | 4 GB | 8 GB | 16+ GB |
| **Storage** | 20 GB SSD | 50 GB SSD | 100+ GB SSD |
| **Network** | 10 Mbps | 50 Mbps | 100+ Mbps |

### Software Requirements

- **Operating System:** Ubuntu 24.04 LTS (Server or Desktop)
- **Python Version:** 3.9.0+ (3.12+ recommended for optimal performance)
- **System Architecture:** x86_64 (AMD64)
- **Network Access:** Outbound HTTPS access to:
  - `clob.polymarket.com` (Polymarket CLOB API)
  - `polygon-rpc.com` (Polygon RPC endpoints)
  - `polygonscan.com` (Transaction monitoring)
  - `api.telegram.org` (Telegram notifications)

### Required System Packages

```bash
# Core Python and build tools
python3 python3-pip python3-venv python3-dev
build-essential libssl-dev libffi-dev pkg-config

# Development libraries for dependencies
libpq-dev libjpeg-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev

# System utilities
git curl wget software-properties-common systemd systemd-resolved
unattended-upgrades apt-transport-https ca-certificates gnupg lsb-release

# Security and monitoring
ufw fail2ban logrotate rsyslog
```

---

## 📦 Prerequisites

### 1. Ubuntu 24.04 Installation

```bash
# Verify Ubuntu version
lsb_release -a

# Expected output:
# Distributor ID: Ubuntu
# Description:    Ubuntu 24.04.x LTS
# Release:        24.04
# Codename:       noble
```

### 2. System Updates

```bash
# Update package lists
sudo apt update

# Upgrade system packages
sudo apt upgrade -y

# Install basic utilities
sudo apt install -y curl wget git software-properties-common
```

### 3. Firewall Configuration

```bash
# Enable UFW
sudo ufw enable

# Allow SSH (adjust port if changed)
sudo ufw allow ssh
sudo ufw allow 22/tcp

# Allow only necessary outbound connections
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Verify firewall status
sudo ufw status verbose
```

---

## 🔧 System Preparation

### Step 1: Install Required System Packages

```bash
# Install all required packages
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    pkg-config \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    git \
    curl \
    wget \
    software-properties-common \
    systemd \
    systemd-resolved \
    unattended-upgrades \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    ufw \
    fail2ban \
    logrotate \
    rsyslog \
    htop \
    iotop \
    ncdu \
    tree \
    jq \
    vim \
    nano
```

### Step 2: Verify Python Installation

```bash
# Check Python version
python3 --version

# Expected: Python 3.12.x or 3.9.x+

# Verify pip installation
python3 -m pip --version

# Upgrade pip to latest version
python3 -m pip install --upgrade pip

# Install virtualenv support
python3 -m pip install virtualenv
```

### Step 3: Create Dedicated Service User

```bash
# Create polymarket-bot user
sudo useradd --system --shell /bin/bash --home /home/polymarket-bot \
    --create-home --user-group polymarket-bot

# Verify user creation
id polymarket-bot

# Expected output: uid=xxx(polymarket-bot) gid=xxx(polymarket-bot) groups=xxx(polymarket-bot)
```

### Step 4: Configure SSH Access (Optional)

```bash
# Create .ssh directory for the service user
sudo mkdir -p /home/polymarket-bot/.ssh
sudo chmod 700 /home/polymarket-bot/.ssh
sudo chown polymarket-bot:polymarket-bot /home/polymarket-bot/.ssh

# If using SSH key authentication, copy authorized_keys
# sudo cp ~/.ssh/authorized_keys /home/polymarket-bot/.ssh/
# sudo chown polymarket-bot:polymarket-bot /home/polymarket-bot/.ssh/authorized_keys
# sudo chmod 600 /home/polymarket-bot/.ssh/authorized_keys
```

---

## 📥 Application Deployment

### Step 1: Download Application Code

```bash
# Switch to service user for deployment
sudo -u polymarket-bot bash

# Create application directory
mkdir -p ~/polymarket-copy-bot
cd ~/polymarket-copy-bot

# Clone or download the application
# Option 1: Git clone (if repository is available)
git clone https://github.com/yourusername/polymarket-copy-bot.git .

# Option 2: Direct download (if using release archives)
# wget https://github.com/yourusername/polymarket-copy-bot/archive/v1.0.0.tar.gz
# tar -xzf v1.0.0.tar.gz --strip-components=1
# rm v1.0.0.tar.gz

# Verify files are in place
ls -la
```

### Step 2: Set Up Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip within virtual environment
pip install --upgrade pip setuptools wheel

# Install Poetry (if using pyproject.toml)
pip install poetry

# Configure Poetry for virtual environment
poetry config virtualenvs.create false
poetry config virtualenvs.in-project true
```

### Step 3: Install Python Dependencies

```bash
# Activate virtual environment (if not already activated)
source venv/bin/activate

# Option 1: Install via Poetry (recommended)
poetry install --no-dev

# Option 2: Install via pip and requirements.txt
# pip install -r requirements.txt

# Verify key dependencies
python -c "import web3; print('Web3 version:', web3.__version__)"
python -c "from py_clob_client import ClobClient; print('Py-Clob-Client imported successfully')"
python -c "import aiohttp; print('aiohttp imported successfully')"
```

### Step 4: Create Required Directories

```bash
# Create application directories
mkdir -p logs data/trades_history monitoring

# Set proper permissions
chmod 750 logs data
chmod 640 logs/* 2>/dev/null || true
chmod 640 data/* 2>/dev/null || true

# Verify directory structure
tree -a -I '.git|venv|__pycache__' -L 2
```

---

## ⚙️ Configuration Setup

### Step 1: Environment Configuration

```bash
# Copy environment template
cp env-staging-template.txt .env

# Edit environment file
nano .env
```

**Required Environment Variables:**

```bash
# Essential Configuration
PRIVATE_KEY=your_ethereum_private_key_here
POLYGON_RPC_URL=https://polygon-rpc.com/
POLYGONSCAN_API_KEY=your_polygonscan_api_key_here

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Polymarket Configuration
CLOB_HOST=https://clob.polymarket.com
CHAIN_ID=137

# Risk Management
MAX_DAILY_LOSS=100.0
MAX_POSITION_SIZE=50.0
STOP_LOSS_PERCENTAGE=10.0

# Monitoring
ENABLE_TELEGRAM_ALERTS=true
LOG_LEVEL=INFO
```

### Step 2: Validate Configuration

```bash
# Test configuration loading
source venv/bin/activate
python -c "from config.settings import settings; settings.validate_critical_settings()"

# Expected output: Configuration validation passed
```

### Step 3: Security Permissions

```bash
# Set restrictive permissions on sensitive files
chmod 600 .env
chmod 600 config/wallets.json
chmod 644 config/settings.py

# Verify permissions
ls -la .env config/wallets.json
```

---

## 🔄 Service Management

### Step 1: Install Systemd Service Files

```bash
# Copy service files to systemd directory
sudo cp systemd/polymarket-bot.service /etc/systemd/system/
sudo cp systemd/polymarket-monitoring.service /etc/systemd/system/
sudo cp systemd/polymarket-monitoring.timer /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable polymarket-bot
sudo systemctl enable polymarket-monitoring.timer
```

### Step 2: Configure Service Permissions

```bash
# Verify service user permissions
sudo systemctl show polymarket-bot -p User,Group,WorkingDirectory

# Test service startup (dry run)
sudo -u polymarket-bot bash -c "cd /home/polymarket-bot/polymarket-copy-bot && source venv/bin/activate && python -c 'print(\"Service user can execute Python\")'"
```

### Step 3: Start Services

```bash
# Start the main bot service
sudo systemctl start polymarket-bot

# Start monitoring timer
sudo systemctl start polymarket-monitoring.timer

# Verify service status
sudo systemctl status polymarket-bot --no-pager -l
sudo systemctl status polymarket-monitoring.timer --no-pager -l
```

---

## 📊 Monitoring Setup

### Step 1: Configure Log Rotation

```bash
# Create logrotate configuration
sudo tee /etc/logrotate.d/polymarket-bot << EOF
/home/polymarket-bot/polymarket-copy-bot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 polymarket-bot polymarket-bot
    postrotate
        systemctl reload polymarket-bot
    endscript
}
EOF

# Test logrotate configuration
sudo logrotate -d /etc/logrotate.d/polymarket-bot
```

### Step 2: Set Up Health Checks

```bash
# Test monitoring scripts
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
source venv/bin/activate
python monitoring/health_check.py
"

# Verify monitoring service
sudo systemctl start polymarket-monitoring
sudo systemctl status polymarket-monitoring --no-pager -l
```

### Step 3: Configure System Monitoring

```bash
# Install monitoring tools
sudo apt install -y prometheus-node-exporter

# Enable node exporter
sudo systemctl enable prometheus-node-exporter
sudo systemctl start prometheus-node-exporter

# Verify node exporter
curl http://localhost:9100/metrics | head -20
```

---

## ✅ Verification & Testing

### Service Verification

```bash
# Check all services status
sudo systemctl status polymarket-bot polymarket-monitoring.timer --no-pager -l

# Verify service logs
sudo journalctl -u polymarket-bot -f --since "1 hour ago" --no-pager | tail -50

# Test service restart capability
sudo systemctl restart polymarket-bot
sleep 5
sudo systemctl status polymarket-bot --no-pager
```

### Application Verification

```bash
# Test configuration validation
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
source venv/bin/activate
python -c 'from config.settings import settings; print(\"Configuration loaded successfully\")'
"

# Test core components
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
source venv/bin/activate
python -c '
from core.clob_client import PolymarketClient
from core.wallet_monitor import WalletMonitor
print(\"Core components imported successfully\")
'
"
```

### Network Connectivity Tests

```bash
# Test Polymarket API connectivity
curl -s https://clob.polymarket.com/info | jq '.'

# Test Polygon RPC connectivity
curl -s -X POST -H "Content-Type: application/json" \
    --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
    https://polygon-rpc.com/ | jq '.'

# Test PolygonScan API
curl -s "https://api.polygonscan.com/api?module=proxy&action=eth_blockNumber" | jq '.'
```

### Performance Verification

```bash
# Check system resources
htop

# Monitor disk usage
df -h /home

# Check memory usage
free -h

# Verify Python performance
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
source venv/bin/activate
python -c '
import asyncio
import time

async def test_async():
    start = time.time()
    await asyncio.sleep(0.1)
    end = time.time()
    print(f\"Async test completed in {end-start:.4f} seconds\")

asyncio.run(test_async())
'
"
```

---

## 🔒 Security Hardening

### Step 1: System Security

```bash
# Install and configure fail2ban
sudo apt install -y fail2ban

# Configure fail2ban for SSH
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Verify fail2ban status
sudo fail2ban-client status
```

### Step 2: Service User Security

```bash
# Remove service user from sudo group (if added during setup)
sudo deluser polymarket-bot sudo

# Verify user permissions
sudo -l -U polymarket-bot

# Expected: No sudo privileges
```

### Step 3: File System Security

```bash
# Set proper ownership
sudo chown -R polymarket-bot:polymarket-bot /home/polymarket-bot/polymarket-copy-bot

# Set restrictive permissions
sudo find /home/polymarket-bot/polymarket-copy-bot -type f -name "*.log" -exec chmod 640 {} \;
sudo find /home/polymarket-bot/polymarket-copy-bot -type f -name "*.json" -exec chmod 600 {} \;
sudo find /home/polymarket-bot/polymarket-copy-bot -type f -name ".env*" -exec chmod 600 {} \;

# Verify permissions
ls -la /home/polymarket-bot/polymarket-copy-bot/.env
```

### Step 4: Network Security

```bash
# Configure firewall for minimal exposure
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 9100/tcp  # Node exporter (if needed)

# Disable unnecessary services
sudo systemctl disable bluetooth.service 2>/dev/null || true
sudo systemctl disable cups.service 2>/dev/null || true

# Verify firewall rules
sudo ufw status verbose
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Service Won't Start

```bash
# Check service status and logs
sudo systemctl status polymarket-bot --no-pager -l
sudo journalctl -u polymarket-bot --since "1 hour ago" --no-pager | tail -50

# Test manual execution
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
source venv/bin/activate
python main.py --help
"
```

#### 2. Import Errors

```bash
# Check Python path and virtual environment
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
source venv/bin/activate
python -c 'import sys; print(sys.path)'
python -c 'import web3, aiohttp, pandas; print(\"Dependencies OK\")'
"
```

#### 3. Permission Errors

```bash
# Fix ownership issues
sudo chown -R polymarket-bot:polymarket-bot /home/polymarket-bot/polymarket-copy-bot

# Check file permissions
ls -la /home/polymarket-bot/polymarket-copy-bot/
```

#### 4. Network Connectivity Issues

```bash
# Test DNS resolution
nslookup clob.polymarket.com

# Test API endpoints
curl -v https://clob.polymarket.com/info

# Check firewall rules
sudo ufw status
```

### Log Analysis

```bash
# View recent logs
sudo journalctl -u polymarket-bot -f --since "10 minutes ago"

# Search for errors
sudo journalctl -u polymarket-bot --grep="ERROR" --since "1 day ago"

# Check application logs
sudo -u polymarket-bot tail -f /home/polymarket-bot/polymarket-copy-bot/logs/bot.log
```

### Performance Issues

```bash
# Monitor system resources
htop
iotop

# Check memory usage
free -h

# Monitor network connections
ss -tuln | grep -E ':(80|443|9100)'
```

---

## 🛠️ Maintenance

### Regular Maintenance Tasks

#### Daily Checks

```bash
# Service status
sudo systemctl status polymarket-bot polymarket-monitoring.timer

# Disk usage
df -h /home

# Log size
sudo du -sh /home/polymarket-bot/polymarket-copy-bot/logs/
```

#### Weekly Tasks

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Clean package cache
sudo apt autoremove -y && sudo apt autoclean

# Rotate logs manually if needed
sudo logrotate -f /etc/logrotate.d/polymarket-bot
```

#### Monthly Tasks

```bash
# Security updates only
sudo unattended-upgrades --dry-run

# Review service logs for anomalies
sudo journalctl -u polymarket-bot --since "30 days ago" | grep -i error | wc -l

# Backup configuration
sudo cp /home/polymarket-bot/polymarket-copy-bot/.env /home/polymarket-bot/.env.backup
```

### Backup Strategy

```bash
# Create backup script
sudo tee /usr/local/bin/polymarket-backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/polymarket-bot/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup configuration and data
tar -czf "$BACKUP_DIR/polymarket_config_$DATE.tar.gz" \
    -C /home/polymarket-bot/polymarket-copy-bot \
    .env config/ data/ logs/

# Keep only last 7 backups
cd "$BACKUP_DIR"
ls -t *.tar.gz | tail -n +8 | xargs -r rm

echo "Backup completed: $BACKUP_DIR/polymarket_config_$DATE.tar.gz"
EOF

# Make executable and test
sudo chmod +x /usr/local/bin/polymarket-backup.sh
sudo /usr/local/bin/polymarket-backup.sh
```

### Update Procedure

```bash
# Stop services
sudo systemctl stop polymarket-bot

# Backup current version
sudo cp -r /home/polymarket-bot/polymarket-copy-bot /home/polymarket-bot/polymarket-copy-bot.backup

# Update code
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
git pull origin main  # or download new version
"

# Update dependencies if needed
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
source venv/bin/activate
pip install -r requirements.txt --upgrade
"

# Test configuration
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
source venv/bin/activate
python -c 'from config.settings import settings; settings.validate_critical_settings()'
"

# Restart services
sudo systemctl start polymarket-bot
sudo systemctl status polymarket-bot --no-pager
```

---

## 📞 Support & Resources

### Log Locations

- **System Logs:** `sudo journalctl -u polymarket-bot`
- **Application Logs:** `/home/polymarket-bot/polymarket-copy-bot/logs/`
- **Monitoring Logs:** `sudo journalctl -u polymarket-monitoring`

### Key Files

- **Service Files:** `/etc/systemd/system/polymarket-bot.service`
- **Configuration:** `/home/polymarket-bot/polymarket-copy-bot/.env`
- **Application Code:** `/home/polymarket-bot/polymarket-copy-bot/`
- **Virtual Environment:** `/home/polymarket-bot/polymarket-copy-bot/venv/`

### Emergency Contacts

- Check Telegram notifications for alerts
- Review logs for error details
- Use health check scripts for diagnostics

---

## ✅ Deployment Checklist

- [ ] Ubuntu 24.04 installed and updated
- [ ] All required system packages installed
- [ ] Dedicated service user created
- [ ] Python virtual environment set up
- [ ] Application code deployed
- [ ] Dependencies installed correctly
- [ ] Configuration files created and validated
- [ ] Environment variables configured
- [ ] Systemd services installed and enabled
- [ ] Firewall configured
- [ ] Security hardening applied
- [ ] Services tested and verified
- [ ] Monitoring and alerting configured
- [ ] Backup strategy implemented

**Deployment completed successfully!** 🎉

---

*This guide ensures a secure, reliable, and maintainable deployment of the Polymarket Copy Trading Bot on Ubuntu 24.04.*
