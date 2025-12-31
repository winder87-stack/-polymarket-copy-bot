# Endgame Sweeper Configuration Guide

## Overview

The Endgame Sweeper is an automated trading strategy that scans for high-probability markets on Polymarket and executes trades with risk management. It's designed for markets with:
- Probability > 95%
- Resolving within 7 days
- Minimum $10K daily liquidity
- High annualized returns

## ⚠️ RISK WARNING

**This strategy carries significant black swan risk:**

1. **Market Cancellation Risk**: Polymarket can cancel markets at any time, potentially resulting in total loss of position.

2. **Outcome Change Risk**: Market outcomes can change unexpectedly, especially for political or sports events.

3. **Liquidity Risk**: In highly illiquid markets, you may not be able to exit at desired prices.

4. **Concentration Risk**: The strategy may concentrate your portfolio in similar markets, increasing correlation risk.

**ALWAYS use proper position sizing and never allocate more than you can afford to lose.**

---

## Configuration Options

### Enable/Disable Endgame Sweeper

```bash
# Enable endgame sweeper (default: false)
ENDGAME_ENABLED=true
```

### Probability Thresholds

```bash
# Minimum probability to consider a market (default: 0.95 = 95%)
ENDGAME_MIN_PROBABILITY=0.95

# Auto-exit when probability reaches this level (default: 0.998 = 99.8%)
# This is a black swan protection mechanism
ENDGAME_MAX_PROBABILITY_EXIT=0.998
```

### Liquidity Requirements

```bash
# Minimum daily liquidity in USDC (default: 10000)
ENDGAME_MIN_LIQUIDITY=10000
```

### Time Constraints

```bash
# Maximum days until market resolution (default: 7)
ENDGAME_MAX_DAYS=7

# Seconds between endgame scans (default: 300 = 5 minutes)
ENDGAME_SCAN_INTERVAL=300
```

### Risk Management

```bash
# Maximum position size as percentage of portfolio (default: 0.03 = 3%)
ENDGAME_MAX_POSITION_PERCENT=0.03

# Stop loss percentage (default: 0.10 = 10%)
# Position automatically closes if it moves 10% against entry
ENDGAME_STOP_LOSS_PERCENT=0.10

# Minimum annualized return percentage (default: 20%)
ENDGAME_MIN_ANNUALIZED_RETURN=20.0
```

---

## Example Configurations

### Conservative Configuration

**Suitable for risk-averse traders who prioritize capital preservation.**

```bash
# Enable endgame sweeper
ENDGAME_ENABLED=true

# Higher probability threshold (97%)
ENDGAME_MIN_PROBABILITY=0.97

# Aggressive exit at 99.5%
ENDGAME_MAX_PROBABILITY_EXIT=0.995

# Higher liquidity requirement ($25K)
ENDGAME_MIN_LIQUIDITY=25000

# Tight time constraint (3 days)
ENDGAME_MAX_DAYS=3

# Very conservative position sizing (1.5%)
ENDGAME_MAX_POSITION_PERCENT=0.015

# Tight stop loss (5%)
ENDGAME_STOP_LOSS_PERCENT=0.05

# Higher annualized return requirement (40%)
ENDGAME_MIN_ANNUALIZED_RETURN=40.0

# Longer scan interval (10 minutes)
ENDGAME_SCAN_INTERVAL=600
```

### Balanced Configuration (Default)

**Recommended for most traders. Balances risk and return.**

```bash
ENDGAME_ENABLED=true
ENDGAME_MIN_PROBABILITY=0.95
ENDGAME_MAX_PROBABILITY_EXIT=0.998
ENDGAME_MIN_LIQUIDITY=10000
ENDGAME_MAX_DAYS=7
ENDGAME_MAX_POSITION_PERCENT=0.03
ENDGAME_STOP_LOSS_PERCENT=0.10
ENDGAME_MIN_ANNUALIZED_RETURN=20.0
ENDGAME_SCAN_INTERVAL=300
```

### Aggressive Configuration

**Suitable for traders with higher risk tolerance seeking maximum returns.**

```bash
ENDGAME_ENABLED=true

# Lower probability threshold (93%)
ENDGAME_MIN_PROBABILITY=0.93

# Less aggressive exit (99.9%)
ENDGAME_MAX_PROBABILITY_EXIT=0.999

# Lower liquidity requirement ($5K)
ENDGAME_MIN_LIQUIDITY=5000

# Longer time window (10 days)
ENDGAME_MAX_DAYS=10

# Larger position sizing (5%)
ENDGAME_MAX_POSITION_PERCENT=0.05

# Wider stop loss (15%)
ENDGAME_STOP_LOSS_PERCENT=0.15

# Lower annualized return requirement (10%)
ENDGAME_MIN_ANNUALIZED_RETURN=10.0

# Faster scan interval (2 minutes)
ENDGAME_SCAN_INTERVAL=120
```

---

## Strategy Logic

### 1. Market Scanning

The sweeper scans all available Polymarket markets and filters for:

```python
# Probability threshold
probability >= ENDGAME_MIN_PROBABILITY (default: 95%)

# Time to resolution
days_to_resolution <= ENDGAME_MAX_DAYS (default: 7)

# Liquidity requirement
liquidity_usdc >= ENDGAME_MIN_LIQUIDITY (default: $10,000)

# Annualized return
annualized_return >= ENDGAME_MIN_ANNUALIZED_RETURN (default: 20%)
```

### 2. Annualized Return Calculation

Annualized return is calculated using the formula:

```
annualized_return = ((1 + edge)^(365/days) - 1) * 100

Where:
edge = (1.00 - probability) * 100
days = days_until_resolution
```

**Example:**
- Probability: 96% (edge = 4%)
- Days to resolution: 7
- Annualized return: 150.8%

### 3. Position Sizing

Position size is calculated as:

```
position_size = min(
    account_balance * ENDGAME_MAX_POSITION_PERCENTAGE,
    MAX_POSITION_SIZE
)
```

The position is scaled based on edge:
- Edge > 5%: Confidence multiplier of 1.5x
- Edge > 3%: Confidence multiplier of 1.2x
- Edge <= 3%: No multiplier (1.0x)

### 4. Exit Conditions

Positions are automatically closed when any of these conditions are met:

#### A. Probability Exit (Black Swan Protection)
```
current_probability >= ENDGAME_MAX_PROBABILITY_EXIT
```
This minimizes risk of last-minute market cancellations.

#### B. Stop Loss
```
abs((current_price - entry_price) / entry_price) >= ENDGAME_STOP_LOSS_PERCENT
```
Closes position if it moves 10% against entry.

#### C. Take Profit
```
abs((current_price - entry_price) / entry_price) >= ENDGAME_STOP_LOSS_PERCENT
```
If price moves 10% in your favor, take profits early.

#### D. Market Resolution
```
days_to_resolution == 0
```
Closes position when market expires.

### 5. Correlation Checking

The sweeper avoids overexposure by:
- Extracting keywords from market questions
- Checking for overlap with existing position keywords
- Skipping markets that share keywords with open positions

---

## Market Blacklist

The following market types are automatically filtered out:

- Elections
- Presidential races
- Voting events
- Congressional/Senate races
- Referendums

These are excluded because they represent obvious public information with low edge.

---

## Performance Metrics

The endgame sweeper tracks:

- Total scans performed
- Opportunities found
- Trades executed
- Successful exits (profit)
- Unsuccessful exits (loss)
- Open positions
- Uptime

View stats with:
```python
from core.endgame_sweeper import EndgameSweeper

stats = endgame_sweeper.get_stats()
print(stats)
```

---

## Integration with Main Bot

The endgame sweeper runs alongside the main copy trading bot:

1. **Main Bot**: Monitors target wallets and copies their trades
2. **Endgame Sweeper**: Independently scans for high-probability opportunities

Both strategies share:
- Circuit breaker (daily loss protection)
- Risk management settings
- Account balance
- Trading infrastructure

### Concurrent Operation

The bot runs both strategies in the monitoring loop:

```python
async def monitor_loop(self):
    while self.running:
        # Main wallet monitoring and copy trading
        await self._monitor_wallets_and_execute_trades()

        # Position management (both strategies)
        await self._manage_positions()

        # Endgame sweeper scan
        await self._run_endgame_sweeper()

        # Maintenance tasks
        await self._perform_maintenance_tasks()
```

---

## Troubleshooting

### No Opportunities Found

If the sweeper never finds opportunities:

1. **Check market availability**: Ensure Polymarket has active markets
2. **Lower thresholds**: Try reducing `ENDGAME_MIN_ANNUALIZED_RETURN`
3. **Check filters**: Verify probability, liquidity, and time thresholds

### Too Many Trades

If executing too many trades:

1. **Increase scan interval**: Set `ENDGAME_SCAN_INTERVAL` higher
2. **Tighten filters**: Increase `ENDGAME_MIN_ANNUALIZED_RETURN`
3. **Reduce position size**: Lower `ENDGAME_MAX_POSITION_PERCENT`

### Circuit Breaker Frequently Triggered

If hitting daily loss limits:

1. **Reduce position size**: Lower `ENDGAME_MAX_POSITION_PERCENT`
2. **Tighten stop loss**: Reduce `ENDGAME_STOP_LOSS_PERCENT`
3. **Increase thresholds**: Only trade markets with higher edge

### Position Liquidity Issues

If having trouble closing positions:

1. **Increase liquidity requirement**: Raise `ENDGAME_MIN_LIQUIDITY`
2. **Auto-exit earlier**: Lower `ENDGAME_MAX_PROBABILITY_EXIT`
3. **Monitor slippage**: Check for excessive price impact on exits

---

## Best Practices

### 1. Start Small

Begin with conservative settings:
- 1% max position size
- Higher annualized return requirement (40%)
- Tighter time constraint (3 days)

### 2. Monitor Performance

Track metrics daily:
- Win rate
- Average return per trade
- Annualized return
- P&L trends

### 3. Adjust Gradually

Make one parameter change at a time:
- Monitor for 1-2 weeks
- Assess impact on performance
- Adjust further if needed

### 4. Set Realistic Expectations

Expected annualized returns:
- Conservative: 50-100%
- Balanced: 100-200%
- Aggressive: 200-500%

**Note: These are gross returns before fees. Net returns will be lower.**

### 5. Use Proper Risk Management

- Never risk more than you can afford to lose
- Diversify across different market types
- Keep enough USDC reserved for slippage
- Monitor circuit breaker status closely

---

## Advanced Configuration

### Custom Blacklist Patterns

To add custom market blacklist patterns, modify:

```python
# In core/endgame_sweeper.py

class EndgameSweeper:
    MARKET_BLACKLIST_PATTERNS = [
        "election",
        "president",
        # Add your custom patterns:
        "specific_event",
        "blacklisted_keyword",
    ]
```

### Custom Exit Strategies

To implement custom exit logic, extend:

```python
# In core/endgame_sweeper.py

async def _check_exit_conditions(self, position, position_key):
    # Add your custom exit logic here

    # Example: Time-based profit taking
    position_age = time.time() - position.entry_time
    if position_age > 3600:  # 1 hour
        # Check if profitable
        if current_price > entry_price * 1.05:  # 5% profit
            return "TIME_PROFIT"

    # Existing exit conditions...
    return existing_exit_reason
```

---

## Monitoring and Alerts

### Telegram Alerts

The bot sends alerts for:
- Trade execution
- Position exit (take profit / stop loss)
- Circuit breaker activation
- Errors and failures

Configure Telegram in `.env`:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Health Checks

Run health checks manually:
```python
# Check endgame sweeper health
healthy = await endgame_sweeper.health_check()

# Check circuit breaker status
cb_state = circuit_breaker.get_state()
print(f"Circuit breaker active: {cb_state['active']}")
print(f"Daily loss: ${cb_state['daily_loss']:.2f}")
```

---

## Frequently Asked Questions

### Q: Should I use the endgame sweeper?

**A:** Only if you:
- Understand the black swan risks
- Have experience with Polymarket
- Can tolerate higher volatility
- Have adequate capital for proper position sizing

### Q: What's the ideal probability threshold?

**A:**
- 95%: More opportunities, higher risk
- 96-97%: Good balance
- 98%+: Fewer opportunities, lower risk

### Q: How much should I allocate to endgame strategy?

**A:** Start with 10-20% of portfolio, monitor performance, then adjust.

### Q: What if a market gets cancelled?

**A:** You'll lose your position value. This is why proper position sizing and circuit breakers are critical.

### Q: Can I run only the endgame sweeper?

**A:** Yes, disable wallet monitoring by setting target_wallets=[] in wallets.json

### Q: How do I know if it's working?

**A:** Check logs for:
- "🎯 Executing endgame trade:" messages
- "✅ Endgame trade executed:" confirmations
- Stats from `endgame_sweeper.get_stats()`

---

## Support and Maintenance

For issues or questions:

1. Check logs: `logs/polymarket_bot.log`
2. Review configuration in `.env`
3. Verify account balance and circuit breaker status
4. Consult main documentation: `README.md`

---

**Remember: This is a high-risk, high-reward strategy. Always use proper risk management and never invest more than you can afford to lose.**
