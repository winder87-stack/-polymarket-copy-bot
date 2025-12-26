# 🚀 Staging Environment Quick Start Guide

## Overview

This guide provides step-by-step instructions for setting up and running the Polymarket Copy Trading Bot in a staging environment on Polygon Mumbai testnet.

**⚠️ IMPORTANT:** This is a STAGING ENVIRONMENT. All trades are on TESTNET only. NEVER use mainnet keys or real funds!

---

## Prerequisites

### System Requirements
- Ubuntu 24.04 LTS server
- Root or sudo access
- Internet connection
- At least 2GB RAM, 20GB storage

### Testnet Requirements
- **Mumbai MATIC**: Get free testnet MATIC from [Polygon Faucet](https://faucet.polygon.technology/)
- **Testnet Wallet**: Create a new wallet for staging (NEVER reuse mainnet wallets)
- **Telegram Bot**: Create a separate Telegram bot for staging alerts

---

## Step 1: Environment Setup

### 1.1 Clone and Setup Project
```bash
# Clone the repository (assuming you're on the server)
git clone <repository-url> polymarket-copy-bot
cd polymarket-copy-bot

# Make scripts executable
chmod +x scripts/*.sh
```

### 1.2 Run Staging Setup Script
```bash
# Run as root or with sudo
sudo ./scripts/setup_staging.sh
```

This script will:
- Create a dedicated `polymarket-staging` user
- Set up Python virtual environment
- Install system dependencies
- Install systemd service
- Set secure file permissions

---

## Step 2: Configuration

### 2.1 Create Environment Configuration
```bash
# Copy the template
cp env-staging-template.txt .env.staging

# Edit with your values
nano .env.staging
```

### 2.2 Required Configuration Values

#### Get Testnet MATIC
```bash
# Visit https://faucet.polygon.technology/
# Request Mumbai MATIC for your staging wallet address
# Wait for confirmation (usually instant)
```

#### Create Telegram Bot for Staging
```bash
# Message @BotFather on Telegram
# Send: /newbot
# Name: Polymarket Staging Bot
# Username: polymarket_staging_bot
# Copy the bot token
```

#### Edit .env.staging
```bash
# REQUIRED: Testnet wallet private key (NEVER use mainnet key!)
STAGING_PRIVATE_KEY=0x0000000000000000000000000000000000000000000000000000000000000000

# REQUIRED: Telegram bot token for staging alerts
STAGING_TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789

# REQUIRED: Telegram chat ID for staging alerts
STAGING_TELEGRAM_CHAT_ID=123456789

# Verify these are set correctly:
STAGING_CHAIN_ID=80001
STAGING_POLYGON_RPC_URL=https://rpc-mumbai.maticvigil.com
```

### 2.3 Validate Configuration
```bash
# Switch to staging user
sudo -u polymarket-staging bash

# Activate virtual environment
cd /home/polymarket-staging/polymarket-copy-bot
source venv/bin/activate

# Test configuration
python config/settings_staging.py

# Expected output:
# ✅ Staging: All critical settings validated successfully
# 🚨 STAGING ENVIRONMENT - TESTNET ONLY 🚨
# Max position size: $5.0
# Max daily loss: $10.0
# Paper trading: false

# Exit staging user
exit
```

---

## Step 3: Pre-Flight Checks

### 3.1 Verify Wallet Balance
```bash
# Check your staging wallet has MATIC
# Visit: https://mumbai.polygonscan.com/
# Search for your wallet address
# Balance should be > 0.1 MATIC
```

### 3.2 Test Telegram Alerts
```bash
# Test staging alerts
sudo -u polymarket-staging bash -c "
cd /home/polymarket-staging/polymarket-copy-bot
source venv/bin/activate
python -c '
import asyncio
from utils.alerts import send_staging_alert
asyncio.run(send_staging_alert(\"🚀 Staging environment test alert\"))
'
"
```

### 3.3 Test RPC Connection
```bash
# Test Mumbai RPC connection
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  https://rpc-mumbai.maticvigil.com/

# Should return current block number
```

---

## Step 4: Start Staging Environment

### 4.1 Enable and Start Service
```bash
# Enable service to start on boot
sudo systemctl enable polymarket-bot-staging

# Start the service
sudo systemctl start polymarket-bot-staging

# Check status
sudo systemctl status polymarket-bot-staging
```

### 4.2 Monitor Startup
```bash
# Watch startup logs
sudo journalctl -u polymarket-bot-staging -f -n 50

# Look for:
# 🚨 STAGING BOT INITIALIZED 🚨
# ✅ Staging: Connected to Polygon Mumbai testnet
# ✅ Staging bot initialization completed
# 🚀 Starting Polymarket Copy Trading Bot (STAGING)...
```

### 4.3 Verify Operation
```bash
# Use the monitoring script
./scripts/monitor_staging.sh status

# Check for alerts in Telegram
# Should receive: "[STAGING] STARTUP: Staging bot started successfully"
```

---

## Step 5: 7-Day Validation Testing

### Daily Monitoring Routine
```bash
# Check status
./scripts/monitor_staging.sh status

# Monitor logs
./scripts/monitor_staging.sh logs

# Run health check
./scripts/monitor_staging.sh health

# Check recent trades
./scripts/monitor_staging.sh trades

# Check alerts
./scripts/monitor_staging.sh alerts
```

### Weekly Validation Tasks

#### End of Day 1
- [ ] Confirm 24-hour uptime
- [ ] Verify at least 1 trade detected
- [ ] Check all alerts received
- [ ] Review error logs

#### End of Day 3
- [ ] Test failure scenarios
- [ ] Verify recovery mechanisms
- [ ] Check data integrity

#### End of Day 7
- [ ] Review all validation criteria
- [ ] Document any issues found
- [ ] Prepare go/no-go decision

### Emergency Procedures

#### Service Restart
```bash
sudo systemctl restart polymarket-bot-staging
```

#### View Detailed Logs
```bash
# Last hour
sudo journalctl -u polymarket-bot-staging --since "1 hour ago"

# Last day with errors
sudo journalctl -u polymarket-bot-staging --since "1 day ago" | grep -E "(ERROR|CRITICAL)"
```

#### Stop Staging Environment
```bash
sudo systemctl stop polymarket-bot-staging
sudo systemctl disable polymarket-bot-staging
```

---

## Troubleshooting

### Common Issues

#### Configuration Errors
```bash
# Check configuration
sudo -u polymarket-staging bash -c "
cd /home/polymarket-staging/polymarket-copy-bot
source venv/bin/activate
python config/settings_staging.py
"
```

#### Service Won't Start
```bash
# Check service status
sudo systemctl status polymarket-bot-staging

# Check logs
sudo journalctl -u polymarket-bot-staging -n 50

# Restart and watch
sudo systemctl restart polymarket-bot-staging
sudo journalctl -u polymarket-bot-staging -f
```

#### No Trades Detected
```bash
# Check target wallets have recent activity
# Verify wallet addresses in config/wallets_staging.json
# Check monitoring interval (30s for staging)
# Review logs for wallet scanning
```

#### Alerts Not Working
```bash
# Test Telegram bot token
curl "https://api.telegram.org/bot$STAGING_TELEGRAM_BOT_TOKEN/getMe"

# Test chat ID
curl "https://api.telegram.org/bot$STAGING_TELEGRAM_BOT_TOKEN/sendMessage?chat_id=$STAGING_TELEGRAM_CHAT_ID&text=Test"

# Check environment variables loaded
sudo systemctl show polymarket-bot-staging -p Environment
```

---

## Security Reminders

### DO NOT:
- ❌ Use mainnet private keys
- ❌ Use real funds
- ❌ Deploy to production servers
- ❌ Skip the 7-day testing period
- ❌ Ignore error alerts

### DO:
- ✅ Use dedicated staging wallet
- ✅ Fund only with testnet MATIC
- ✅ Monitor logs and alerts daily
- ✅ Test failure scenarios
- ✅ Document all issues found

---

## Next Steps

After successful 7-day staging validation:

1. **Review Results**: Check `STAGING_VALIDATION_PLAN.md` criteria
2. **Go/No-Go Decision**: Assess readiness for mainnet
3. **Production Setup**: Use staging-validated configuration
4. **Deploy to Production**: Follow mainnet deployment procedures

---

## Support

### During Staging Testing
- Check logs: `./scripts/monitor_staging.sh logs`
- Health checks: `./scripts/monitor_staging.sh health`
- Alert history: `./scripts/monitor_staging.sh alerts`

### Emergency Contacts
- Development Team: For technical issues
- Infrastructure Team: For server/network issues
- Security Team: For security concerns

---

**🚨 Remember: STAGING = TESTNET ONLY 🚨**

*This guide ensures safe and effective staging environment setup and testing.*
