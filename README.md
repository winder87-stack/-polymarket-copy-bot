# 🤖 Polymarket Copy Trading Bot

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04-orange.svg)](https://ubuntu.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.1-blue.svg)]()

A production-ready bot that monitors hand-picked wallets on Polymarket and automatically replicates their trades. Built with security, reliability, and risk management as top priorities.

## ⚠️ **DISCLAIMER**

**This software is for educational purposes only. Trading cryptocurrencies involves substantial risk of loss. Use at your own risk. The authors are not responsible for any losses incurred while using this software.**

## 🔧 Features

- **Real-time Wallet Monitoring**: Track transactions from targeted wallets using Polygon blockchain data
- **Smart Trade Replication**: Automatically copy trades with configurable risk parameters
- **Comprehensive Risk Management**:
  - Daily loss limits with circuit breaker protection
  - Dynamic position sizing based on account balance and price risk
  - Stop loss and take profit automation
  - Slippage protection and gas optimization
  - Concurrent position limits
- **Production-Grade Infrastructure**:
  - Systemd service integration for reliable operation
  - Comprehensive logging with security-conscious data handling
  - Telegram alerts for trades, errors, and system events
  - Health checks and automatic recovery mechanisms
  - Rate limiting for external API calls
  - Dry-run mode for safe testing
- **Advanced Trading Features**:
  - Confidence score filtering for trade quality
  - Market maker detection and specialized handling
  - Adaptive strategy engine with multiple wallet type profiles
  - Backtesting engine for strategy validation
  - Performance analytics and reporting

## 📊 System Status

**Version:** 1.0.1 (Latest Stable)
**Python:** 3.12+ Required
**Ubuntu:** 24.04 LTS Recommended
**Status:** Production Ready ✅

### ✅ **Verified Working Features**

- ✅ Real-time wallet monitoring with rate limiting
- ✅ Automated trade execution with risk management
- ✅ Circuit breaker protection (tested and working)
- ✅ Position sizing with edge case handling
- ✅ Telegram alerts and notifications
- ✅ Comprehensive logging and error handling
- ✅ Dry-run mode for safe testing
- ✅ Systemd service integration

### 🔄 **Recent Improvements** (v1.0.1)

- 🐛 Fixed critical division by zero in position sizing
- 🔒 Enhanced security with input sanitization
- 📈 Improved performance with optimized API calls
- 🧪 Added comprehensive unit test coverage
- 📚 Updated documentation and examples

## 🛠️ Troubleshooting Guide

### Common Issues and Solutions

#### **Bot Won't Start**

- **Symptoms:** Service fails immediately, logs show import errors
- **Solutions:**
  1. Check virtual environment: `source venv/bin/activate`
  2. Verify dependencies: `pip install -r requirements.txt`
  3. Check .env file syntax and required variables
  4. Validate config: `python -c "from config.settings import settings; settings.validate_critical_settings()"`

#### **No Trades Detected**

- **Symptoms:** Bot runs but never detects any trades
- **Solutions:**
  1. Verify Polygonscan API key is valid and not rate-limited
  2. Check target wallet addresses in `config/wallets.json`
  3. Ensure MONITOR_INTERVAL is reasonable (15-60 seconds)
  4. Check blockchain connection: `curl https://polygon-rpc.com`
  5. Enable DEBUG logging to see raw transaction data

#### **Trades Fail to Execute**

- **Symptoms:** Trades detected but order placement fails
- **Solutions:**
  1. Check account balance: insufficient USDC or MATIC for gas
  2. Verify private key has trading permissions
  3. Check gas prices aren't exceeding MAX_GAS_PRICE
  4. Ensure CLOB_HOST is correct for testnet/mainnet
  5. Review circuit breaker status (daily loss limits)

#### **High Memory Usage**

- **Symptoms:** Memory usage grows steadily over time
- **Solutions:**
  1. Restart bot daily: `sudo systemctl restart polymarket-bot`
  2. Reduce number of monitored wallets
  3. Increase MONITOR_INTERVAL to reduce transaction volume
  4. Upgrade server memory (minimum 2GB recommended)

## 📋 System Requirements

| Component | Minimum Version | Recommended Version | Notes |
|-----------|----------------|---------------------|-------|
| Ubuntu | 22.04 LTS | 24.04 LTS | 24.04 has better Python 3.12 support |
| Python | 3.10 | 3.12 | 3.12 has asyncio performance improvements |
| web3.py | 6.0.0 | 6.17.0 | Required for Polygon blockchain interaction |
| py-clob-client | 0.5.0 | 0.6.0 | Official Polymarket CLOB API client |
| Node.js | Not required | Not required | Pure Python implementation |
| PostgreSQL | Not required | Not required | SQLite used for local storage |

## 🔧 Quick Start

### Prerequisites

- Ubuntu 24.04 server or desktop
- Python 3.12+
- Polygon wallet with USDC funds
- Telegram account (optional but recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/polymarket-copy-bot.git
cd polymarket-copy-bot

# Install dependencies
pip install -r requirements.txt

# Configure environment (copy and edit template)
cp env-template.txt .env
nano .env  # Fill in your configuration values

# Run validation tests
python3 test_trade_validation.py
python3 test_position_manager.py
python3 test_rate_limiter.py

# Start the bot (dry-run mode first!)
python3 main.py
```

### Configuration

Copy `env-template.txt` to `.env` and configure:

```env
# Required
PRIVATE_KEY=your_private_key_here
POLYGONSCAN_API_KEY=your_api_key_here

# Trading Settings
MAX_POSITION_SIZE=10.0          # Start small!
MAX_DAILY_LOSS=50.0            # Conservative limit
DRY_RUN=true                   # Test first!

# Monitoring
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
MONITOR_INTERVAL=30
```

---

**💡 Pro Tip:** Always start with testnet and small amounts. Monitor closely for the first week before increasing position sizes. The bot is designed for educational purposes - never risk more than you can afford to lose.

**🔍 Transparency Note:** We believe in honest disclosure of limitations. If you discover an issue not listed here, please [open an issue](https://github.com/winder87-stack/polymarket-copy-bot/issues) so we can address it and update this documentation.

## 🚀 Quick Start

### Prerequisites

- Ubuntu 24.04 server or desktop
- Python 3.12+
- Polygon wallet with USDC funds (testnet first!)

### Installation

```bash
# Clone the repository
git clone https://github.com/winder-87-stack/polymarket-copy-bot.git
cd polymarket-copy-bot

# Run setup script (requires sudo)
sudo ./scripts/setup_ubuntu.sh

# Configure your environment variables
cp .env.example .env
nano .env  # Fill in your configuration values (USE TESTNET FIRST!)

# Start the bot
sudo systemctl start polymarket-bot

# Check logs
journalctl -u polymarket-bot -f -n 100
```

### Testing

Before going live, run the comprehensive test suite:

```bash
# Run unit tests
python3 test_position_manager.py     # Position sizing edge cases
python3 test_rate_limiter.py         # Rate limiting verification
python3 test_trade_validation.py     # Trade validation logic

# Run integration tests
python3 integration_test.py          # Full system integration
python3 integration_check.py         # Component validation

# Run validation suite
python3 final_system_validation.py    # Production readiness check
```

### Production Deployment

```bash
# Install systemd service
sudo cp systemd/polymarket-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable polymarket-bot

# Start with dry-run mode
sudo systemctl start polymarket-bot
sudo systemctl status polymarket-bot

# Monitor logs
journalctl -u polymarket-bot -f
```

## 🧪 Risk Management

### Safety Features

- **Circuit Breaker**: Automatic shutdown on excessive losses
- **Position Limits**: Maximum position size controls
- **Slippage Protection**: Configurable slippage limits
- **Rate Limiting**: API throttling to prevent bans
- **Dry Run Mode**: Safe testing without real trades

### Recommended Settings for New Users

```env
MAX_POSITION_SIZE=1.0          # $1 per trade initially
MAX_DAILY_LOSS=5.0            # $5 daily loss limit
DRY_RUN=true                  # Always test first!
MIN_CONFIDENCE_SCORE=0.8      # Only high-confidence trades
```

---

**💡 Pro Tip:** Start with testnet (Mumbai) and small amounts. Monitor for 24-48 hours before enabling live trading. Never risk more than you can afford to lose.

**🔍 Support:** Found a bug or have questions? Check the [CHANGELOG.md](CHANGELOG.md) first, then [open an issue](https://github.com/yourusername/polymarket-copy-bot/issues).
