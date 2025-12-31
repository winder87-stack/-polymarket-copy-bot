#!/bin/bash
# setup_environment.sh
set -e

echo "🔧 Setting up Polymarket Copy Bot Environment Variables"
echo "══════════════════════════════════════════════════════════"

ENV_FILE=".env"

# Create .env file if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example "$ENV_FILE"
        echo "✅ Created $ENV_FILE from template"
    else
        touch "$ENV_FILE"
        echo "✅ Created empty $ENV_FILE (no template found)"
    fi
fi

# Function to set environment variable if not already set
set_env_var() {
    local key=$1
    local value=$2
    local description=$3

    if ! grep -q "^$key=" "$ENV_FILE"; then
        echo "$key=$value" >> "$ENV_FILE"
        echo "✅ Set $key: $description"
    else
        echo "⏭️  $key already configured"
    fi
}

# Core Trading Settings
echo -e "\n🎯 CORE TRADING SETTINGS"
set_env_var "PRIVATE_KEY" "your_private_key_here" "Ethereum private key for trading"
set_env_var "POLYGON_RPC_URL" "https://falling-solitary-research.matic.quiknode.pro/fa518d685fd0c4d00c5d3284da3bb7d63f046e14" "QuickNode RPC endpoint (production-ready)"
set_env_var "DRY_RUN" "true" "Start in safe mode - NO REAL TRADES"

# Risk Management
echo -e "\n🛡️  RISK MANAGEMENT SETTINGS"
set_env_var "MAX_POSITION_SIZE" "1.0" "Maximum position size in USDC (start small!)"
set_env_var "MAX_DAILY_LOSS" "5.0" "Maximum daily loss limit in USDC"
set_env_var "SLIPPAGE_TOLERANCE" "0.02" "Maximum slippage (2%)"

# Scanner Settings
echo -e "\n📊 SCANNER SETTINGS"
set_env_var "POLYMARKET_API_KEY" "your_polymarket_api_key_here" "Polymarket leaderboard API key"
set_env_var "POLYGONSCAN_API_KEY" "your_polygonscan_api_key_here" "PolygonScan API key for transaction monitoring"
set_env_var "SCAN_INTERVAL_HOURS" "6" "How often to rescan leaderboards"
set_env_var "MAX_WALLETS_TO_MONITOR" "25" "Maximum wallets to track"

# Alerting & Monitoring
echo -e "\n🔔 ALERTING & MONITORING"
set_env_var "TELEGRAM_BOT_TOKEN" "your_telegram_bot_token" "Telegram bot token for alerts"
set_env_var "TELEGRAM_CHAT_ID" "your_telegram_chat_id" "Your Telegram chat ID"
set_env_var "LOG_LEVEL" "INFO" "Logging level (DEBUG, INFO, WARNING, ERROR)"

# Performance & Memory
echo -e "\n⚡ PERFORMANCE & MEMORY SETTINGS"
set_env_var "MEMORY_LIMIT_MB" "1024" "Memory limit before auto-restart (critical for memory leak mitigation)"
set_env_var "MONITOR_INTERVAL" "30" "Wallet monitoring interval in seconds"

echo -e "\n📋 ENVIRONMENT SETUP COMPLETE"
echo "══════════════════════════════════"

echo -e "\n⚠️  IMPORTANT NEXT STEPS:"
echo "1. Edit $ENV_FILE and replace placeholder values with your actual credentials"
echo "2. START WITH TESTNET FIRST! Change to mainnet only after thorough testing"
echo "3. Keep DRY_RUN=true until you've verified all components work correctly"
echo "4. Set conservative risk limits initially (MAX_POSITION_SIZE=1.0, MAX_DAILY_LOSS=5.0)"

echo -e "\n🔍 Verification command:"
echo "python -c \"import os; print('Environment variables loaded:', all(key in os.environ for key in ['PRIVATE_KEY', 'POLYGON_RPC_URL', 'POLYMARKET_API_KEY']))\""
