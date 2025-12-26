# Environment Configuration Guide

This guide explains how to safely configure your Polymarket Copy Bot environment.

## 🚨 Security Notice

**NEVER commit actual API keys, private keys, or sensitive data to version control.**

The `.env` file contains sensitive information and is automatically ignored by Git.

## 📋 Setup Instructions

### 1. Copy Environment Template

```bash
# Copy the template to create your .env file
cp .env.template .env
```

### 2. Configure Required Settings

Edit `.env` with your actual values:

```bash
# Required: Polygon Network Access
POLYGON_RPC_URL=https://polygon-mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID
POLYGONSCAN_API_KEY=YOUR_POLYGONSCAN_API_KEY

# Required: Trading Wallet (KEEP SECURE!)
TRADING_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
TRADING_WALLET_ADDRESS=0xYOUR_WALLET_ADDRESS_HERE

# Optional: Telegram Notifications
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

### 3. Environment Variables Reference

#### Required Variables

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `POLYGON_RPC_URL` | Polygon blockchain RPC endpoint | [Infura](https://infura.io/), [Alchemy](https://alchemy.com/), or other providers |
| `POLYGONSCAN_API_KEY` | API key for Polygonscan | [Polygonscan API](https://polygonscan.com/apis) |
| `TRADING_PRIVATE_KEY` | Private key for trading wallet | Your wallet's private key (KEEP SECURE!) |
| `TRADING_WALLET_ADDRESS` | Trading wallet address | Derived from private key |

#### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot notifications | Disabled |
| `TELEGRAM_CHAT_ID` | Telegram chat for notifications | Disabled |
| `LOG_LEVEL` | Logging verbosity | INFO |
| `ENABLE_TRADING` | Enable live trading | false |
| `MAX_POSITION_SIZE` | Max position size (0.01 = 1%) | 0.05 |
| `STOP_LOSS_PERCENTAGE` | Stop loss threshold | 0.05 |
| `TARGET_WALLETS` | Wallets to monitor | Empty |

## 🔐 Security Best Practices

### Private Key Security
- **Never share your private key**
- **Never commit private keys to version control**
- **Use hardware wallets when possible**
- **Rotate keys regularly**

### API Key Security
- **Use read-only API keys when possible**
- **Set appropriate rate limits**
- **Monitor API usage**
- **Rotate keys if compromised**

### Environment Security
- **Keep .env files out of version control**
- **Use strong, unique encryption keys**
- **Limit file permissions** (`chmod 600 .env`)
- **Never run as root**

## 🧪 Testing Configuration

Test your configuration:

```bash
# Validate configuration
python scripts/validate_config.py

# Test environment template
python scripts/check_env_template.py

# Run basic health check
python -c "from core.clob_client import PolymarketClient; client = PolymarketClient(); print('✅ Configuration valid' if client.health_check() else '❌ Configuration invalid')"
```

## 🚨 Emergency Procedures

If you suspect your keys have been compromised:

1. **Immediately disable trading**: Set `ENABLE_TRADING=false`
2. **Rotate API keys** from provider dashboards
3. **Generate new wallet** and transfer funds
4. **Change all passwords** and access tokens
5. **Monitor for unauthorized transactions**

## 📞 Support

For configuration issues:
- Check the [README.md](README.md) for detailed setup instructions
- Review [security hardening guide](security_hardening_guide.md)
- Test with `ENABLE_TRADING=false` first

Remember: **Security first** - take your time to configure properly! 🔒
