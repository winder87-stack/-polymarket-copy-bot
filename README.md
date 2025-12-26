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

## 🚀 Quick Start

### Prerequisites
- Ubuntu 24.04 server or desktop
- Python 3.12+
- Polygon wallet with USDC funds (testnet first!)

### Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/polymarket-copy-bot.git
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
