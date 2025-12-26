# Polymarket Copy Trading Bot - Cursor Context

## Project Overview
This is a production-ready **Polymarket Copy Trading Bot** that monitors wallet transactions on Polygon blockchain and automatically replicates trades using the Polymarket CLOB (Central Limit Order Book) API.

## Architecture & Tech Stack
- **Language**: Python 3.12+
- **Framework**: Web3.py + Polymarket CLOB Client
- **Blockchain**: Polygon (Matic) Network
- **Configuration**: Pydantic + dotenv
- **Async Runtime**: asyncio with uvloop
- **Security**: Cryptography library with secure logging
- **Monitoring**: Telegram alerts + comprehensive logging

## Key Components

### Core Modules
- **`main.py`**: Application entry point with graceful shutdown handling
- **`core/clob_client.py`**: Polymarket API client with retry logic and caching
- **`core/wallet_monitor.py`**: Blockchain transaction monitoring
- **`core/trade_executor.py`**: Trade execution with risk management
- **`config/settings.py`**: Configuration management with validation

### Utilities
- **`utils/security.py`**: Secure logging and credential masking
- **`utils/alerts.py`**: Telegram notification system
- **`utils/helpers.py`**: Blockchain utilities and conversions
- **`utils/logging_utils.py`**: Structured logging configuration

## Development Environment

### Virtual Environment
The project uses a Python virtual environment in `./venv/`. Always activate it:
```bash
source venv/bin/activate
```

### Configuration
Environment variables are loaded from `.env` file. Critical variables:
- `PRIVATE_KEY`: Your Polygon wallet private key
- `POLYGON_RPC_URL`: Polygon RPC endpoint
- `TELEGRAM_BOT_TOKEN`: For notifications
- `CLOB_HOST`: Polymarket API endpoint

### Testing Structure
```
tests/
├── unit/          # Unit tests for individual components
├── integration/   # API integration tests
└── conftest.py    # Test configuration
```

## Security Considerations
- **Never commit private keys** - they're flagged by `.cursorrules`
- **Use secure logging** - sensitive data is automatically masked
- **Environment isolation** - all secrets loaded from environment
- **Input validation** - all financial operations are validated

## Development Workflow

### Running the Bot
1. Configure your `.env` file with proper credentials
2. Activate virtual environment: `source venv/bin/activate`
3. Run: `python main.py`

### Testing
- Unit tests: `python -m pytest tests/unit/`
- Integration tests: `python -m pytest tests/integration/`
- All tests: `python -m pytest tests/`

### Production Deployment
- Uses systemd service: `systemd/polymarket-bot.service`
- Setup script: `scripts/setup_ubuntu.sh`
- Health monitoring: `scripts/health_check.sh`

## Risk Management Features
- **Position sizing**: Configurable max position size
- **Daily loss limits**: Circuit breaker functionality  
- **Slippage protection**: Automatic price adjustment
- **Confidence scoring**: Trade detection validation
- **Rate limiting**: API call throttling

## Monitoring & Alerting
- **Telegram notifications**: Trade alerts and errors
- **Structured logging**: JSON-formatted logs with context
- **Performance metrics**: Trade success rates and P&L tracking
- **Health checks**: Component status monitoring

## Key Patterns Used
- **Async/await everywhere**: All I/O operations are async
- **Dependency injection**: Components receive dependencies
- **Configuration validation**: Pydantic models with validators
- **Retry logic**: Tenacity decorators for external API calls
- **Context managers**: Proper resource management
- **Type hints**: Full type annotation coverage

## Cursor IDE Rules
This project uses `.cursorrules` for code quality enforcement:
- Security-sensitive data detection
- Gas optimization reminders
- Error handling requirements
- Type hint enforcement
- Async pattern validation
- Web3 address validation
- Decimal precision warnings

## Common Development Tasks

### Adding New Features
1. Create feature branch from main
2. Implement in appropriate module
3. Add unit tests
4. Update documentation
5. Test integration

### Debugging Issues
1. Check logs in `logs/` directory
2. Use VS Code debugger configurations
3. Enable verbose logging with `LOG_LEVEL=DEBUG`
4. Check health status with health check script

### Performance Optimization
1. Monitor async operations for blocking calls
2. Check gas prices and optimize transactions
3. Review caching effectiveness
4. Analyze trade execution times

## Important Reminders
- **Always test on testnet first** before mainnet deployment
- **Monitor gas prices** - high gas can drain your wallet
- **Keep position sizes small** when starting
- **Regular backup** of configuration and logs
- **Monitor error rates** and alert thresholds

## Support & Documentation
- Check `README.md` for setup instructions
- Review `config/settings.py` for all configuration options
- Use VS Code debugger for development
- Check systemd logs: `journalctl -u polymarket-bot -f`
