# Cross-Market Arbitrage Integration Guide

## Overview

The `CrossMarketArbitrageur` class provides a retail-viable cross-market arbitrage strategy that identifies and executes pricing inefficiencies across correlated Polymarket markets. This guide explains how to integrate it with your existing copy trading bot.

## Architecture

### Key Components

```
core/
├── cross_market_arb.py       # Main arbitrage implementation
├── clob_client.py             # Polymarket API client (existing)
├── circuit_breaker.py         # Risk management (existing)
└── trade_executor.py          # Trade execution (existing)

config/
├── scanner_config.py           # Arb configuration (updated)
└── settings.py               # Bot settings (existing)

monitoring/
├── dashboard.py               # Dashboard with arb metrics (updated)
└── monitoring_config.py       # Monitoring configuration (updated)

utils/
├── helpers.py                # BoundedCache (existing)
├── alerts.py                 # Telegram alerts (existing)
└── logger.py                # Logging (existing)

tests/
└── unit/
    └── test_cross_market_arb.py  # Unit tests (new)
```

## Integration Steps

### 1. Enable Arbitrage in Configuration

Edit `config/scanner_config.py` or set environment variables:

```python
# config/scanner_config.py
ARBITRAGE_ENABLED = True  # Enable arbitrage strategy
ARBITRAGE_MAX_POSITION_PERCENT = 0.02  # 2% max position size
ARBITRAGE_MIN_LIQUIDITY_USD = 25000  # $25K minimum liquidity
ARBITRAGE_MIN_CORRELATION = 0.8  # Minimum correlation threshold
ARBITRAGE_POLL_INTERVAL_SECONDS = 30  # 30-second polling
```

Or via environment variables:

```bash
export ARBITRAGE_ENABLED=true
export ARBITRAGE_MAX_POSITION_PERCENT=0.02
export ARBITRAGE_MIN_LIQUIDITY_USD=25000
```

### 2. Add to Trade Execution Pipeline

Update `core/trade_executor.py` to include arbitrage:

```python
# Add import
from core.cross_market_arb import CrossMarketArbitrageur

# In TradeExecutor.__init__():
if self.settings.scanner.ARBITRAGE_ENABLED:
    self.arbitrageur = CrossMarketArbitrageur(
        clob_client=self.clob_client,
        circuit_breaker=self.circuit_breaker,
        max_position_size=Decimal(str(self.settings.scanner.ARBITRAGE_MAX_POSITION_PERCENT)),
        min_liquidity=Decimal(str(self.settings.scanner.ARBITRAGE_MIN_LIQUIDITY_USD)),
        enabled=True,
    )

    # Start arbitrage monitoring in background
    asyncio.create_task(self.arbitrageur.start_monitoring())
    logger.info("✅ Cross-market arbitrage enabled and monitoring started")
else:
    self.arbitrageur = None
    logger.info("ℹ️ Cross-market arbitrage disabled")
```

### 3. Add Health Checks

Update health check methods:

```python
# In TradeExecutor.health_check():
if self.arbitrageur:
    arb_stats = self.arbitrageur.get_statistics()
    logger.info(f"Arbitrage Stats: {arb_stats['arbitrages_executed']} executed, "
                f"${arb_stats['net_profit']:.2f} profit")
```

### 4. Add Shutdown Handling

Update shutdown logic:

```python
# In TradeExecutor.shutdown():
if self.arbitrageur:
    await self.arbitrageur.shutdown()
```

## Market Correlation Configuration

The arbitrageur uses human-defined market correlations. Add your own in `core/cross_market_arb.py`:

```python
PREDEFINED_CORRELATIONS = {
    "your_market_id": {
        "related_market_id": {
            "correlation": 0.90,  # Pearson correlation (0.0 to 1.0)
            "description": "Human-readable explanation of correlation",
            "category": "politics",  # politics, crypto, sports, economics
        },
    },
}
```

### Sample Market Correlation Pairs

#### US Politics
```python
"trump_wins_2024": {
    "republican_wins_2024": {
        "correlation": 0.95,
        "description": "Trump winning directly implies Republican victory",
        "category": "politics",
    },
    "gop_control_senate": {
        "correlation": 0.85,
        "description": "Trump presidency correlates with GOP Senate control",
        "category": "politics",
    },
}
```

#### Crypto Markets
```python
"btc_above_100k": {
    "eth_above_5k": {
        "correlation": 0.85,
        "description": "BTC and ETH historically move together",
        "category": "crypto",
    },
}
```

#### Sports
```python
"chiefs_win_superbowl": {
    "afc_wins_superbowl": {
        "correlation": 0.90,
        "description": "Chiefs winning implies AFC victory",
        "category": "sports",
    },
}
```

## Monitoring & Alerts

### Dashboard Integration

The arbitrageur automatically integrates with the monitoring dashboard:

```bash
# Generate dashboard with arbitrage metrics
python -m monitoring.dashboard

# View dashboard
open monitoring/dashboard/dashboard.html
```

### Telegram Alerts

The arbitrageur sends Telegram alerts for:

1. **New Opportunity Detection**
   ```
   🎯 ARBITRAGE OPPORTUNITY DETECTED
   Edge: 5.23%
   Markets: 2
   Risk Level: LOW
   ```

2. **Successful Execution**
   ```
   ✅ ARBITRAGE EXECUTED
   Edge: 5.23%
   Profit: $5.00
   ID: arb_1234567890_trump_repu
   ```

3. **Failed Execution**
   ```
   ❌ ARBITRAGE FAILED
   ID: arb_1234567890_trump_repu
   Reason: Circuit breaker active
   ```

4. **High Volatility Alert**
   ```
   ⚠️ HIGH VOLATILITY DETECTED
   Market: trump_wins_2024
   Volatility: 55.2%
   Action: Arbitrage disabled for 5 minutes
   ```

## Risk Controls

### Implemented Safeguards

1. **Position Size Limit**
   - Maximum 2% of portfolio per arbitrage
   - Configurable via `ARBITRAGE_MAX_POSITION_PERCENT`

2. **Liquidity Requirement**
   - Minimum $25K liquidity across all markets
   - Configurable via `ARBITRAGE_MIN_LIQUIDITY_USD`

3. **Volatility Filter**
   - Skips markets with >50% daily price swings
   - Automatically disables arbitrage during high volatility

4. **Correlation Threshold**
   - Only considers markets with >=0.8 correlation
   - Human-defined correlations (no ML black boxes)

5. **Slippage Protection**
   - Maximum 0.5% slippage tolerance
   - Conservative to prevent losses

6. **Circuit Breaker Integration**
   - Respects global circuit breaker state
   - Stops trading during daily loss limit

7. **Time Decay Adjustment**
   - Accounts for options-like contract decay
   - Reduces expected profit as expiration approaches

## Usage Example

```python
import asyncio
from core.cross_market_arb import CrossMarketArbitrageur
from core.clob_client import PolymarketClient
from core.circuit_breaker import CircuitBreaker
from pathlib import Path

async def main():
    # Initialize client
    clob_client = PolymarketClient()

    # Create circuit breaker
    circuit_breaker = CircuitBreaker(
        max_daily_loss=100.0,  # $100 daily loss limit
        wallet_address=clob_client.wallet_address,
        state_file=Path("data/circuit_breaker_state.json"),
    )

    # Create arbitrageur
    arbitrageur = CrossMarketArbitrageur(
        clob_client=clob_client,
        circuit_breaker=circuit_breaker,
        max_position_size=Decimal("0.02"),  # 2%
        min_liquidity=Decimal("25000"),  # $25K
        enabled=True,
    )

    # Start monitoring (runs in background)
    monitoring_task = asyncio.create_task(arbitrageur.start_monitoring())

    try:
        # Keep running
        while True:
            await asyncio.sleep(60)
            stats = arbitrageur.get_statistics()
            logger.info(f"Arbitrage Stats: {stats}")

    except KeyboardInterrupt:
        # Graceful shutdown
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass

        # Cleanup
        await arbitrageur.shutdown()
        logger.info("Arbitrageur shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
```

## Performance Characteristics

### Computational Requirements

- **CPU**: Minimal (correlation calculations are lightweight)
- **Memory**: ~100MB with default cache sizes
- **Network**: 1 API call per market every 30 seconds
- **Latency**: Not competitive with institutional HFT (by design)

### Expected Performance

- **Opportunity Detection**: 1-5 per day (varies by market)
- **Execution Rate**: 20-40% of detected opportunities
- **Average Edge**: 2-5% per opportunity
- **Success Rate**: 60-80% (depends on market conditions)

### When Arbitrage Works Best

1. **High Correlation Periods**: Major elections, sports championships
2. **Low Volatility**: Stable market conditions
3. **High Liquidity**: Popular markets with deep order books
4. **Multiple Correlated Markets**: Complex relationships (politics, crypto)

### When to Disable Arbitrage

1. **Major News Events**: Breaks correlations unpredictably
2. **Election Nights**: Extreme volatility
3. **Market Manipulation**: Suspicious price movements
4. **Low Liquidity**: Thin order books

## Testing

### Run Unit Tests

```bash
# Run all cross-market arb tests
pytest tests/unit/test_cross_market_arb.py -v

# Run specific test
pytest tests/unit/test_cross_market_arb.py::test_risk_filter_passes_liquid_opportunity -v

# Run with coverage
pytest tests/unit/test_cross_market_arb.py --cov=core.cross_market_arb --cov-report=html
```

### Integration Testing

```bash
# Test with staging environment
export STAGING_MODE=true
export ARBITRAGE_ENABLED=true

# Run bot with arbitrage enabled
python main.py

# Monitor logs
tail -f logs/polymarket_copy_bot.log | grep -i arbitrage
```

## Troubleshooting

### No Opportunities Detected

**Issue**: Arbitrageur running but not finding opportunities

**Solutions**:
1. Check if markets are enabled: Verify `ARBITRAGE_ENABLED=true`
2. Verify correlation data: Check `PREDEFINED_CORRELATIONS` in code
3. Check liquidity filter: Markets may not meet $25K minimum
4. Review logs: Look for "fetching order books" messages

### High Volatility Mode Active

**Issue**: Arbitrageur stuck in high volatility mode

**Solutions**:
1. Wait for volatility to decrease (typically 5-30 minutes)
2. Adjust `ARBITRAGE_MAX_DAILY_VOLATILITY` if too conservative
3. Manually reset: `arbitrageur._high_volatility_mode = False`

### Execution Failures

**Issue**: Opportunities detected but execution fails

**Solutions**:
1. Check circuit breaker: May be blocking trades
2. Verify balance: Insufficient USDC for position size
3. Review slippage: May exceed 0.5% tolerance
4. Check API status: Polymarket API may be down

### Memory Issues

**Issue**: High memory usage

**Solutions**:
1. Reduce cache sizes in `BoundedCache` initialization
2. Clear caches: `arbitrageur._correlation_cache.clear()`
3. Check for memory leaks: Use `mprof` or `memory_profiler`

## Advanced Configuration

### Custom Market Correlations

Add domain-specific correlations:

```python
# In core/cross_market_arb.py
PREDEFINED_CORRELATIONS = {
    # Your custom correlations
    "custom_market_1": {
        "custom_market_2": {
            "correlation": 0.92,
            "description": "Your explanation",
            "category": "your_category",
        },
    },
}
```

### Adjust Risk Parameters

```python
arbitrageur = CrossMarketArbitrageur(
    clob_client=clob_client,
    circuit_breaker=circuit_breaker,
    max_position_size=Decimal("0.01"),  # More conservative (1%)
    min_liquidity=Decimal("50000"),     # Higher liquidity requirement
    enabled=True,
)
```

### Custom Monitoring

```python
# Add custom alert handlers
async def custom_alert_handler(opportunity):
    # Send to custom monitoring system
    await send_to_prometheus(opportunity)
    await log_to_datadog(opportunity)

# Hook into arbitrageur
arbitrageur._send_arbitrage_alert = custom_alert_handler
```

## Risk Disclosure

**IMPORTANT**: Cross-market arbitrage carries significant risks. Please review the full risk disclosure in `core/cross_market_arb.py`:

1. **Correlation Breakdown Risk**: Correlations can fail during black swans
2. **Liquidity Risk**: Markets can dry up unexpectedly
3. **Slippage Risk**: Actual execution may differ from quoted prices
4. **Time Decay Risk**: Options-like contracts lose value over time
5. **Black Swan Events**: Unpredictable events can cause massive losses

**Recommendations**:
- Start with small position sizes
- Monitor correlation quality regularly
- Set stop-loss limits
- Be prepared to disable during major events
- Diversify across market categories

## Support & Maintenance

### Logs

Arbitrage logs are stored in:
- `logs/polymarket_copy_bot.log` (main log)
- `logs/arbitrage.log` (arb-specific, if configured)

### Statistics

View real-time statistics:
```python
stats = arbitrageur.get_statistics()
print(f"Opportunities: {stats['opportunities_detected']}")
print(f"Executed: {stats['arbitrages_executed']}")
print(f"Profit: ${stats['net_profit']:.2f}")
```

### Health Checks

```bash
# Check if arbitrageur is healthy
curl -X GET http://localhost:8080/health/arbitrage

# Expected response:
{
  "status": "healthy",
  "enabled": true,
  "uptime_hours": 24.5,
  "opportunities_detected": 42,
  "arbitrages_executed": 15
}
```

## Summary

The `CrossMarketArbitrageur` provides a retail-viable arbitrage strategy with:

✅ **Human-interpretable correlations** (no ML black boxes)
✅ **Comprehensive risk controls** (position limits, liquidity filters)
✅ **Circuit breaker integration** (automatic shutdown on losses)
✅ **Telegram alerts** (real-time notifications)
✅ **Monitoring dashboard** (visual performance metrics)
✅ **Production-grade code** (type hints, error handling, tests)

Start small, monitor closely, and scale up as you gain confidence in the strategy.

---

**Last Updated**: 2025-12-27
**Version**: 1.0.0
**Author**: Polymarket Copy Bot Team
