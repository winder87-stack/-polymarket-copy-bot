# Multi-Account Setup Guide

This guide explains how to configure and use multiple trading accounts for risk distribution and portfolio management.

## Overview

The multi-account system allows you to:

- **Distribute risk** across multiple wallets
- **Allocate trades** based on percentage distribution
- **Isolate risk management** per account
- **Track balances** and performance separately
- **Unified reporting** across all accounts

## Architecture

The multi-account system consists of:

1. **AccountManager** (`config/account_manager.py`): Manages wallet profiles and balance tracking
2. **StrategyAllocator** (`core/strategy_allocator.py`): Distributes trades across accounts
3. **MultiAccountDashboard** (`monitoring/multi_account_dashboard.py`): Unified reporting
4. **AccountsConfig** (`config/accounts_config.py`): Configuration schema

## Backward Compatibility

The system maintains **full backward compatibility** with single-account configurations:

- If no accounts config is provided, the system uses the single account from `settings.trading`
- Existing single-account setups continue to work without changes
- Migration to multi-account is optional and non-breaking

## Configuration

### Option 1: JSON Configuration File

Create `config/accounts.json`:

```json
{
  "accounts": [
    {
      "account_id": "conservative_account",
      "private_key": "0x...",
      "enabled": true,
      "allocation_percentage": 50.0,
      "min_balance_usdc": 10.0,
      "tags": ["conservative"],
      "risk_config": {
        "max_position_size": 25.0,
        "max_daily_loss": 50.0,
        "min_trade_amount": 1.0,
        "max_concurrent_positions": 5,
        "stop_loss_percentage": 0.10,
        "take_profit_percentage": 0.20
      }
    },
    {
      "account_id": "aggressive_account",
      "private_key": "0x...",
      "enabled": true,
      "allocation_percentage": 50.0,
      "min_balance_usdc": 10.0,
      "tags": ["aggressive"],
      "risk_config": {
        "max_position_size": 50.0,
        "max_daily_loss": 100.0,
        "min_trade_amount": 2.0,
        "max_concurrent_positions": 10,
        "stop_loss_percentage": 0.15,
        "take_profit_percentage": 0.25
      }
    }
  ],
  "default_risk_config": {
    "max_position_size": 50.0,
    "max_daily_loss": 100.0,
    "min_trade_amount": 1.0,
    "max_concurrent_positions": 10,
    "stop_loss_percentage": 0.15,
    "take_profit_percentage": 0.25,
    "max_slippage": 0.02
  }
}
```

### Option 2: Environment Variables

Set `ACCOUNTS_CONFIG_PATH` to point to your config file:

```bash
export ACCOUNTS_CONFIG_PATH=/path/to/accounts.json
```

Or provide JSON directly:

```bash
export ACCOUNTS_CONFIG_JSON='{"accounts": [...]}'
```

### Option 3: Programmatic Setup

```python
from config.account_manager import AccountManager, WalletProfile
from config.settings import settings

# Initialize account manager
account_manager = AccountManager(settings)

# Add accounts
profile1 = WalletProfile(
    account_id="account_1",
    wallet_address="0x...",
    private_key="0x...",
    enabled=True,
    allocation_percentage=50.0,
    min_balance_usdc=10.0,
)

profile2 = WalletProfile(
    account_id="account_2",
    wallet_address="0x...",
    private_key="0x...",
    enabled=True,
    allocation_percentage=50.0,
    min_balance_usdc=10.0,
)

account_manager.add_account(profile1)
account_manager.add_account(profile2)
```

## Configuration Fields

### Account Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `account_id` | string | Yes | Unique identifier for the account |
| `private_key` | string | Yes | Private key for signing transactions |
| `wallet_address` | string | No | Wallet address (auto-derived if not provided) |
| `enabled` | boolean | No | Whether account is active (default: true) |
| `allocation_percentage` | float | No | Percentage of trades allocated (0-100, default: 100.0) |
| `min_balance_usdc` | float | No | Minimum balance threshold (default: 10.0) |
| `max_balance_usdc` | float | No | Maximum balance threshold (optional) |
| `tags` | array | No | Tags for categorizing accounts |
| `metadata` | object | No | Additional metadata |
| `risk_config` | object | No | Account-specific risk configuration overrides |

### Risk Configuration

Account-specific risk config overrides global settings:

| Field | Type | Description |
|-------|------|-------------|
| `max_position_size` | float | Maximum USDC per position |
| `max_daily_loss` | float | Circuit breaker threshold |
| `min_trade_amount` | float | Minimum trade amount |
| `max_concurrent_positions` | int | Maximum open positions |
| `stop_loss_percentage` | float | Stop loss percentage (0.01-0.5) |
| `take_profit_percentage` | float | Take profit percentage (0.01-1.0) |
| `max_slippage` | float | Maximum slippage (0.001-0.1) |

## Allocation Strategy

### Percentage-Based Allocation

Trades are allocated based on `allocation_percentage`:

- **Example**: Account 1: 50%, Account 2: 50%
  - Trade of $100 → Account 1: $50, Account 2: $50

- **Example**: Account 1: 70%, Account 2: 30%
  - Trade of $100 → Account 1: $70, Account 2: $30

### Allocation Rules

1. **Balance Check**: Accounts must have sufficient balance for their allocation
2. **Minimum Trade Amount**: Each allocation must meet the account's minimum trade amount
3. **Enabled Accounts Only**: Only enabled accounts receive allocations
4. **Normalization**: If percentages don't sum to 100%, they are normalized

### Allocation Validation

The system validates that:
- Allocation percentages sum to 100% (within tolerance)
- All accounts have sufficient balance
- All allocations meet minimum trade amounts

## Usage Examples

### Basic Setup

```python
from config.account_manager import AccountManager
from config.settings import settings

# Initialize (loads from config/accounts.json if exists)
account_manager = AccountManager(settings)

# Get enabled accounts
enabled_accounts = account_manager.get_enabled_accounts()

# Get total balance
total_balance = account_manager.get_total_balance()
```

### Trade Allocation

```python
from core.strategy_allocator import StrategyAllocator

# Create allocator
allocator = StrategyAllocator(account_manager)

# Allocate a trade
original_trade = {
    "tx_hash": "0x123...",
    "amount": 100.0,
    "price": 0.5,
}

allocations = await allocator.allocate_trade(
    original_trade,
    trade_amount=Decimal("100.0")
)

# Execute trades for each allocation
for allocation in allocations:
    # Create CLOB client for this account
    account = account_manager.get_account(allocation.account_id)
    clob_client = PolymarketClient(
        private_key=account.private_key,
        wallet_address=allocation.wallet_address
    )

    # Execute trade
    result = await clob_client.place_order(
        condition_id=original_trade["condition_id"],
        side=original_trade["side"],
        amount=float(allocation.allocation_amount),
        price=original_trade["price"],
    )
```

### Unified Reporting

```python
from monitoring.multi_account_dashboard import MultiAccountDashboard

# Create dashboard
dashboard = MultiAccountDashboard(account_manager, allocator)

# Get unified report
report = await dashboard.get_unified_report()

# Format for display
formatted = await dashboard.format_report_for_display(report)
print(formatted)

# Get account-specific report
account_report = await dashboard.get_account_performance_report("account_1")

# Get risk alerts
alerts = await dashboard.get_risk_alerts()
```

## Balance Tracking

Balances are automatically tracked per account:

```python
# Update balance (typically called after trade execution)
await account_manager.update_balance(
    account_id="account_1",
    balance_usdc=Decimal("100.0"),
    source="api"
)

# Get balance
balance = await account_manager.get_balance("account_1")

# Get total balance across all accounts
total = account_manager.get_total_balance()
```

## Risk Management

Each account can have isolated risk management:

```python
# Get account-specific risk config
risk_config = account_manager.get_account_risk_config("account_1")

# Risk config includes:
# - max_position_size
# - max_daily_loss
# - min_trade_amount
# - max_concurrent_positions
# - stop_loss_percentage
# - take_profit_percentage
# - max_slippage
```

## Monitoring and Alerts

### Risk Alerts

The dashboard provides risk alerts:

```python
alerts = await dashboard.get_risk_alerts()

# Alert types:
# - low_balance: Account below minimum balance threshold
# - high_balance: Account above maximum balance threshold
```

### Performance Metrics

Unified metrics include:

- Total balance across all accounts
- Per-account balance and P&L
- Allocation statistics
- Risk summary
- Performance trends

## Migration from Single Account

To migrate from single-account to multi-account:

1. **Create accounts config** (`config/accounts.json`)
2. **Add your existing account** with `allocation_percentage: 100.0`
3. **Add additional accounts** as needed
4. **Restart the bot**

The system will automatically:
- Detect the accounts config
- Load accounts
- Use multi-account allocation

Your existing single account continues to work during migration.

## Best Practices

1. **Allocation Percentages**: Ensure they sum to 100% for predictable distribution
2. **Balance Thresholds**: Set appropriate `min_balance_usdc` to prevent over-trading
3. **Risk Config**: Use account-specific risk configs for different strategies
4. **Tags**: Use tags to categorize accounts (e.g., "conservative", "aggressive")
5. **Monitoring**: Regularly check unified reports and risk alerts

## Troubleshooting

### No Accounts Found

If no accounts are configured, the system falls back to single-account mode using `settings.trading`.

### Allocation Percentages Don't Sum to 100%

The system will warn but continue. Percentages are normalized automatically.

### Insufficient Balance

Accounts with insufficient balance are filtered out during allocation. Ensure accounts have adequate balance.

### Account Not Enabled

Disabled accounts are excluded from allocation. Check `enabled` field in config.

## Security Considerations

1. **Private Keys**: Never commit private keys to version control
2. **File Permissions**: Restrict access to `config/accounts.json` (chmod 600)
3. **Environment Variables**: Use environment variables for sensitive data
4. **State File**: The state file contains balance data but not private keys

## API Reference

See code documentation in:
- `config/account_manager.py`
- `core/strategy_allocator.py`
- `monitoring/multi_account_dashboard.py`
- `config/accounts_config.py`

## Examples

See `tests/test_multi_account_integration.py` for complete examples.
