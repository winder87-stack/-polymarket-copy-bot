# 🤖 Polymarket Copy Trading Bot

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04-orange.svg)](https://ubuntu.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI/CD](https://github.com/yourusername/polymarket-copy-bot/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/yourusername/polymarket-copy-bot/actions)

A production-ready bot that monitors 25 hand-picked wallets on Polymarket and automatically replicates their trades. Built with security, reliability, and risk management as top priorities.

## ⚠️ **DISCLAIMER**

**This software is for educational purposes only. Trading cryptocurrencies involves substantial risk of loss. Use at your own risk. The authors are not responsible for any losses incurred while using this software.**

## 🔧 Features

- **Real-time Wallet Monitoring**: Track transactions from 25+ wallets using Polygon blockchain data
- **Smart Trade Replication**: Automatically copy trades with configurable risk parameters
- **Comprehensive Risk Management**:
  - Daily loss limits (circuit breakers)
  - Position sizing based on account balance
  - Stop loss and take profit automation
  - Slippage protection
- **Production-Grade Infrastructure**:
  - Systemd service integration
  - Comprehensive logging and monitoring
  - Telegram alerts for trades and errors
  - Health checks and automatic recovery

## ⚠️ Known Issues & Limitations

This section documents current limitations and known issues. We're actively working on improvements, but transparency is important for production deployments.

### 🔴 Critical Limitations

#### **Circuit Breaker Logic Bug** (Fixed in v1.0.1)

- **Issue:** Previous versions had a critical bug where circuit breakers would either crash the bot or skip all trades
- **Impact:** Could cause complete trading halt or uncontrolled trading
- **Status:** Fixed in commit [abc123] - update immediately if using older versions
- **Workaround:** None - requires code update

#### **Division by Zero Risk** (Fixed in v1.0.1)

- **Issue:** Position sizing could cause extremely large trades when price movement is minimal
- **Impact:** Could lead to catastrophic losses in stable markets
- **Status:** Fixed with proper bounds checking and Decimal precision
- **Workaround:** Set conservative MAX_POSITION_SIZE in .env file

### 🟠 High Priority Issues Being Addressed

#### **Memory Leaks in Position Tracking**

- **Issue:** Position locks and transaction caches grow unbounded over time
- **Impact:** Memory usage increases steadily, eventually causing Out of Memory errors after 24-48 hours
- **Status:** In progress - fixed position locks, working on transaction cache optimization
- **Workaround:** Restart the bot daily using systemd service: `sudo systemctl restart polymarket-bot`
- **ETA:** v1.1.0 (Q1 2025)

#### **Broad Exception Handling**

- **Issue:** Too many `except Exception` blocks mask root causes of failures
- **Impact:** Difficult to debug issues in production environments
- **Status:** Refactoring in progress to use specific exception types
- **Workaround:** Check detailed logs in `logs/polymarket_bot.log` and enable DEBUG level logging
- **ETA:** v1.1.0 (Q1 2025)

#### **API Rate Limit Bypass in Concurrent Calls**

- **Issue:** Concurrent API calls can bypass Polygonscan rate limits
- **Impact:** API keys can be temporarily banned, causing trade detection failures
- **Status:** Implementing proper rate limiting with semaphores
- **Workaround:** Reduce MONITOR_INTERVAL to 30+ seconds and limit to 10 wallets maximum
- **ETA:** v1.1.0 (Q1 2025)

### 🟡 Medium Priority Limitations

#### **No WebSocket Support**

- **Issue:** Current implementation polls for transactions instead of using WebSockets
- **Impact:** 15-30 second delay in trade detection, missing rapid trades
- **Status:** Planning WebSocket integration for v1.2.0
- **Workaround:** None - inherent limitation of polling architecture
- **ETA:** v1.2.0 (Q2 2025)

#### **Limited Gas Optimization**

- **Issue:** Gas price calculation lacks advanced optimization strategies
- **Impact:** Higher gas costs than manual trading, especially during volatile periods
- **Status:** Researching MEV protection and gas optimization algorithms
- **Workaround:** Set MAX_GAS_PRICE conservatively (50-100 gwei) to avoid high gas trades
- **ETA:** v1.3.0 (Q3 2025)

#### **Single Account Limitation**

- **Issue:** Bot can only manage one trading account at a time
- **Impact:** Cannot distribute risk across multiple wallets or use separate wallets for different strategies
- **Status:** Architecture planned for multi-account support
- **Workaround:** Run multiple bot instances with different .env files and service names
- **ETA:** v2.0.0 (Q4 2025)

### 🟢 Low Priority Known Issues

#### **Documentation Gaps**

- **Issue:** Some functions lack comprehensive docstrings
- **Impact:** Harder for new developers to contribute
- **Status:** Ongoing documentation improvement effort
- **Workaround:** Read code and existing examples
- **ETA:** Continuous improvement

#### **Code Style Inconsistencies**

- **Issue:** Some PEP-8 violations and inconsistent formatting
- **Impact:** Minor readability issues
- **Status:** Pre-commit hooks being configured
- **Workaround:** None needed for functionality
- **ETA:** v1.1.0 (Q1 2025)

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

## 📋 Version Compatibility Matrix

| Component | Minimum Version | Recommended Version | Notes |
|-----------|----------------|---------------------|-------|
| Ubuntu | 22.04 LTS | 24.04 LTS | 24.04 has better Python 3.12 support |
| Python | 3.10 | 3.12 | 3.12 has performance improvements |
| web3.py | 6.0.0 | 6.17.0 | Required for Polygon support |
| py-clob-client | 0.5.0 | 0.6.0 | Official Polymarket client |
| Node.js | Not required | Not required | Pure Python implementation |
| PostgreSQL | Not required | Not required | SQLite used for local storage |

## 🗓️ Development Roadmap

### Q1 2025 (v1.1.0)

- [ ] Fix all memory leak issues
- [ ] Improve error handling and logging
- [ ] Add comprehensive unit tests
- [ ] Implement proper rate limiting
- [ ] Complete API documentation

### Q2 2025 (v1.2.0)

- [ ] WebSocket integration for real-time trade detection
- [ ] Advanced gas optimization strategies
- [ ] Performance monitoring dashboard
- [ ] Multi-chain support (Arbitrum, Base)

### Q3 2025 (v1.3.0)

- [ ] MEV protection features
- [ ] Portfolio optimization algorithms
- [ ] Machine learning for trade quality scoring
- [ ] Mobile app for monitoring and alerts

### Q4 2025 (v2.0.0)

- [ ] Multi-account support
- [ ] Institutional-grade security features
- [ ] Regulatory compliance tools
- [ ] Cloud deployment templates

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
