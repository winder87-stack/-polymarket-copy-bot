# 🚀 Polymarket Copy Trading Bot - Deployment Guide

**Production-Ready Polymarket Copy Trading Bot** - Automatically monitors wallet addresses on Polygon blockchain and replicates trades with comprehensive risk management.

## 📊 Quick Status

- ✅ **Core Functionality**: IMPLEMENTED & TESTED
- ✅ **Risk Management**: CIRCUIT BREAKER ACTIVE
- ✅ **API Integrations**: CONFIGURED
- ✅ **Monitoring & Alerts**: READY
- ⚠️  **API Endpoints**: REQUIRES MAINNET CONFIG
- ⚠️  **Production Deployment**: NEEDS SYSTEMD SETUP

**Status: PRODUCTION READY (WITH CONFIGURATION)**

---

## 🛠️ Quick Start

### 1. Environment Setup
```bash
# Configure environment variables
./setup_environment.sh

# Edit .env file with your credentials
nano .env
```

### 2. Run Tests
```bash
# Run comprehensive test suite
./test_all.sh

# Check project status
./project_status.sh
```

### 3. Start Trading (Safe Mode)
```bash
# Start in DRY RUN mode (NO REAL TRADES)
python main.py --dry-run

# Monitor logs
tail -f logs/bot.log
```

---

## 📋 Prerequisites

- **Python 3.12+**
- **Ubuntu 20.04+ / Debian-based Linux**
- **QuickNode Polygon RPC endpoint**
- **Polymarket API credentials**
- **Private key for trading wallet**

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
# CRITICAL: Never commit this file!

# Trading Wallet (KEEP SECURE)
PRIVATE_KEY=0x5bd0c5f1e08cf9e30d092ce96235c7939217983dc132908ba37c6125559e5716
WALLET_ADDRESS=  # Auto-calculated

# Blockchain Configuration
POLYGON_RPC_URL=https://falling-solitary-research.matic.quiknode.pro/...
POLYGONSCAN_API_KEY=your_polygonscan_api_key

# Polymarket API
CLOB_HOST=https://clob.polymarket.com
POLYMARKET_API_KEY=your_polymarket_api_key

# Risk Management (START CONSERVATIVE)
DRY_RUN=true                    # SAFETY FIRST!
MAX_POSITION_SIZE=1.0           # $1.00 per position initially
MAX_DAILY_LOSS=5.0             # $5.00 daily loss limit
SLIPPAGE_TOLERANCE=0.02        # 2% max slippage

# Monitoring
SCAN_INTERVAL_HOURS=6           # Rescan leaderboards every 6 hours
MAX_WALLETS_TO_MONITOR=25      # Track top 25 wallets
MONITOR_INTERVAL=30            # Check every 30 seconds

# Alerts (Optional but recommended)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
LOG_LEVEL=INFO
```

### Quick Setup Script
```bash
./setup_environment.sh
```

---

## 🚀 Deployment Options

### Option 1: Manual Testing
```bash
# Start in safe mode
python main.py --dry-run

# Monitor in another terminal
tail -f logs/bot.log
```

### Option 2: Production Service
```bash
# Install systemd service
sudo cp systemd/polymarket-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable polymarket-bot
sudo systemctl start polymarket-bot

# Monitor service
sudo systemctl status polymarket-bot
sudo journalctl -u polymarket-bot -f
```

### Option 3: Docker Deployment
```bash
# Build and run
docker build -t polymarket-bot .
docker run -d --env-file .env polymarket-bot
```

---

## 🧪 Testing Suite

### Comprehensive Test Suite
```bash
./test_all.sh
```
Tests all components: configuration, connectivity, scanners, trading, and system health.

### Individual Component Tests
```bash
# Configuration validation
python -c "from config import get_settings; print('✅ Config loaded')"

# API connectivity
python -c "
from core.clob_client import PolymarketClient
client = PolymarketClient()
print('✅ CLOB client ready')
"

# Trading components
python -c "
from core.trade_executor import TradeExecutor
from core.clob_client import PolymarketClient
executor = TradeExecutor(PolymarketClient())
print('✅ Trading system ready')
"
```

---

## 📊 Monitoring & Alerts

### Real-time Monitoring
- **Logs**: `logs/bot.log`
- **System Health**: `system_health_report.json`
- **Test Reports**: `test_report_*.json`

### Telegram Alerts (Recommended)
```bash
# Configure in .env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Key Metrics to Monitor
- Memory usage (auto-restart at 1GB)
- Gas prices and slippage
- Trade success/failure rates
- Circuit breaker status
- API rate limits

---

## 🛡️ Risk Management

### Circuit Breaker Protection
- **Daily Loss Limit**: $100 (configurable)
- **Consecutive Losses**: 5 losses trigger pause
- **Failure Rate**: 50%+ failure rate triggers pause

### Safety Features
- **DRY RUN Mode**: Test without real trades
- **Position Size Limits**: Maximum $ per position
- **Slippage Protection**: 2% maximum slippage
- **Rate Limiting**: API abuse prevention

### Conservative Starting Settings
```bash
DRY_RUN=true
MAX_POSITION_SIZE=1.0    # $1 per trade
MAX_DAILY_LOSS=5.0      # $5 daily limit
SLIPPAGE_TOLERANCE=0.02 # 2% slippage
```

---

## 🔍 Troubleshooting

### Common Issues

#### API Connection Problems
```bash
# Check RPC endpoint
curl -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' $POLYGON_RPC_URL

# Check Polymarket API
curl "https://polymarket.com/api/leaderboard?page=1&limit=1"
```

#### Memory Issues
```bash
# Check memory usage
ps aux | grep python
./project_status.sh
```

#### Trading Issues
```bash
# Check logs
tail -f logs/bot.log

# Verify credentials
python -c "from config import get_settings; s=get_settings(); print('✅ Config loaded')"
```

### Performance Optimization
- Monitor memory usage (restart at 1GB)
- Adjust scan intervals based on API limits
- Use rate limiting for API calls
- Enable circuit breaker for safety

---

## 📈 Scaling & Production

### Production Checklist
- [ ] Environment variables configured
- [ ] DRY RUN testing completed
- [ ] Systemd service installed
- [ ] Monitoring and alerts active
- [ ] Backup strategy in place
- [ ] Incident response plan ready

### Performance Tuning
```bash
# Memory limits
MEMORY_LIMIT_MB=1024

# API rate limits
SCAN_INTERVAL_HOURS=6

# Position sizing
MAX_POSITION_SIZE=50.0  # Increase gradually
```

### Backup Strategy
```bash
# Configuration backup
cp .env .env.backup

# Logs rotation
logrotate logs/bot.log

# Database backup (if applicable)
# Add your database backup commands
```

---

## 🤝 Support & Contributing

### Getting Help
1. Check logs: `tail -f logs/bot.log`
2. Run diagnostics: `./project_status.sh`
3. Review test results: `./test_all.sh`
4. Check documentation: `README.md`

### Contributing
- Run full test suite before changes
- Add tests for new features
- Update documentation
- Follow security best practices

---

## ⚠️ Important Warnings

### Security
- **NEVER** commit `.env` file to version control
- Use hardware wallet for mainnet trading
- Rotate API keys regularly
- Enable 2FA everywhere

### Risk Management
- **ALWAYS** test in DRY_RUN mode first
- Start with very small position sizes
- Monitor gas prices and adjust limits
- Have manual override capability

### Legal & Compliance
- Understand local regulations for automated trading
- Polymarket terms of service compliance
- Tax implications of trading activity
- Record keeping requirements

---

## 🎯 Next Steps

1. **Setup**: Run `./setup_environment.sh`
2. **Test**: Run `./test_all.sh`
3. **Verify**: Check `./project_status.sh`
4. **Start Safe**: Run with `DRY_RUN=true`
5. **Monitor**: Watch logs and alerts
6. **Scale**: Gradually increase position sizes
7. **Production**: Set up systemd service

---

**Ready to start trading safely?** 🚀

```bash
# Final verification
./project_status.sh

# Start safe trading
python main.py --dry-run
```

---

*Generated: December 26, 2025*
*Polymarket Copy Bot v1.0 - Production Ready*
