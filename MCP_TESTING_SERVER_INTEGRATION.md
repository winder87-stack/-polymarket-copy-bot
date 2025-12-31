# Testing MCP Server - Integration Guide

## Overview

The `testing_server` MCP server provides comprehensive test execution and coverage reporting for Polymarket Copy Bot project. It includes real-time monitoring, automatic test generation, and integration with the circuit breaker system for production safety.

### Key Features

- **Async Test Execution**: Non-blocking test runs with timeout protection
- **Real-time Monitoring**: Dashboard endpoint for test status
- **Automatic Test Generation**: Generate tests for new trading strategies
- **Circuit Breaker Integration**: Test safety during high load
- **Resource Limits**: 2GB memory, 4 CPU cores, 5-minute timeout
- **Coverage Reporting**: 85% minimum target with alerting on drops
- **Thread Safety**: All operations use async/await with proper locking
- **Telegram Alerts**: Immediate notification on test failures

## Installation & Setup

### 1. Dependencies

The testing server requires pytest and coverage tools. Install with:

```bash
pip install -r requirements.txt
```

Required packages:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
- `pytest-timeout` - Test timeout protection

### 2. Configuration

Configuration is managed via `config/mcp_config.py`. The server uses these environment variables:

| Environment Variable | Default | Description |
|-------------------|----------|-------------|
| `TESTING_SERVER_ENABLED` | `true` | Enable testing MCP server |
| `COVERAGE_TARGET` | `0.85` | Minimum coverage target (85%) |
| `RUN_ON_COMMIT` | `true` | Run tests on commit |
| `RUN_ON_PR` | `true` | Run tests on pull request |
| `ALERT_ON_COVERAGE_DROP` | `true` | Alert when coverage drops below target |

Add to your `.env` file:

```bash
TESTING_SERVER_ENABLED=true
COVERAGE_TARGET=0.85
RUN_ON_COMMIT=true
RUN_ON_PR=true
ALERT_ON_COVERAGE_DROP=true
```

### 3. Pre-Commit Hooks

Install pre-commit hooks:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
```

Pre-commit hooks include:
- **Linting**: Ruff for code quality
- **Type Checking**: MyPy for type safety
- **Testing**: Run critical tests before commit
- **Security**: Bandit for security scanning
- **Money Safety**: Check for float() usage in money calculations
- **API Keys**: Prevent committing API keys or secrets

### 4. GitHub Actions

The `.github/workflows/test.yml` provides automated testing on:
- Every push to `main` or `develop` branches
- All pull requests targeting `main` or `develop`

Workflows include:
- **Critical Tests**: Tests for `trade_executor`, `circuit_breaker`, `market_analyzer`, `wallet_monitor`
- **Integration Tests**: Full system integration tests
- **Coverage Report**: Combined coverage with threshold checking
- **Security Scan**: Bandit and safety checks
- **Performance Tests**: Benchmark execution
- **Notifications**: Telegram alerts on test results

## Usage

### Programmatic Usage

#### Basic Test Execution

```python
import asyncio
from mcp.testing_server import TestingServer

async def run_tests():
    server = TestingServer()

    # Run all critical tests
    results = await server.run_critical_tests()

    for module, result in results.items():
        print(f"{module}:")
        print(f"  Passed: {result.passed}/{result.total_tests}")
        print(f"  Coverage: {result.coverage:.1%}")
        print(f"  Duration: {result.duration_seconds:.2f}s")

    await server.shutdown()

asyncio.run(run_tests())
```

#### Run Specific Modules

```python
async def run_specific_tests():
    server = TestingServer()

    # Run only specific modules
    results = await server.run_critical_tests(
        modules=[
            "tests.unit.test_trade_executor",
            "tests.unit.test_circuit_breaker",
        ]
    )

    for module, result in results.items():
        if result.failed + result.errors > 0:
            print(f"❌ {module} failed")
        else:
            print(f"✅ {module} passed")

    await server.shutdown()

asyncio.run(run_specific_tests())
```

#### Get Test Dashboard Data

```python
import asyncio
from mcp.testing_server import get_testing_server

async def show_dashboard():
    server = get_testing_server()

    # Get real-time dashboard data
    dashboard = await server.get_test_dashboard_data()

    print("Test Dashboard:")
    print(f"  Total Tests Run: {dashboard['total_tests_run']}")
    print(f"  Success Rate: {dashboard['success_rate']:.1%}")
    print(f"  Circuit Breaker: {dashboard['circuit_breaker_state']}")
    print(f"  Last Coverage Drop: {dashboard['last_coverage_drop']}")

    await server.shutdown()

asyncio.run(show_dashboard())
```

#### Generate Tests for New Strategies

```python
import asyncio
from mcp.testing_server import get_testing_server

async def generate_strategy_tests():
    server = get_testing_server()

    # Generate tests for endgame sweeper
    test_file = await server.generate_tests_for_strategy("endgame_sweeper")
    print(f"✅ Generated tests at: {test_file}")

    # Generate tests for quality whale copy
    test_file = await server.generate_tests_for_strategy("quality_whale")
    print(f"✅ Generated tests at: {test_file}")

    # Generate tests for cross-market arbitrage
    test_file = await server.generate_tests_for_strategy("cross_market_arbitrage")
    print(f"✅ Generated tests at: {test_file}")

    await server.shutdown()

asyncio.run(generate_strategy_tests())
```

### CLI Usage

While the testing server is primarily programmatic, you can run tests via pytest CLI:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_trade_executor.py -v

# Run with coverage
pytest tests/ --cov=core --cov-report=term-missing

# Run with timeout
pytest tests/ --timeout=120

# Run only fast tests
pytest tests/ -m "not slow"
```

### Testing via GitHub Actions

Tests run automatically on push/PR. To trigger manually:

1. Go to Actions tab in GitHub
2. Select "Testing Workflow"
3. Click "Run workflow"
4. Select branch and click "Run"

## Critical Test Coverage

### Money Safety Tests

Ensure all financial calculations use `Decimal`, not `float`:

```python
# ✅ CORRECT
from decimal import Decimal

account_balance = Decimal("10000.0")
risk_percent = Decimal("0.01")
position_size = account_balance * risk_percent

# ❌ WRONG - Never use float for money
account_balance = 10000.0
risk_percent = 0.01
position_size = account_balance * risk_percent  # Uses float!
```

Tests verify:
- All money-related variables use `Decimal`
- No `float()` calls with money variables
- High precision (28 decimal places)
- Proper rounding (ROUND_HALF_UP)

### Memory Safety Tests

Verify `BoundedCache` prevents memory leaks:

```python
# ✅ CORRECT
from utils.helpers import BoundedCache

cache = BoundedCache(
    max_size=1000,  # Limit entries
    ttl_seconds=3600,  # 1 hour TTL
    memory_threshold_mb=50.0,  # Alert at 50MB
)

# ❌ WRONG - Unbounded cache grows forever
cache = {}  # Will cause memory leak
```

Tests verify:
- Cache has max_size limit
- TTL-based expiration works
- Memory threshold triggers cleanup
- Old entries are evicted (LRU)

### Risk Control Tests

Verify circuit breaker trips after 3 consecutive losses:

```python
# Test scenario
from core.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(
    max_daily_loss=100.0,
    wallet_address="0x...",
)

# Record 3 consecutive losses
await breaker.record_loss(10.0)  # Loss 1
await breaker.record_loss(15.0)  # Loss 2
await breaker.record_loss(20.0)  # Loss 3 - should trip!

# Check state
state = breaker.get_state()
assert state["active"] == True
assert state["consecutive_losses"] == 3
```

Tests verify:
- Circuit breaker activates at threshold
- Daily loss limit triggers circuit
- Cooldown period works correctly
- State transitions are atomic

### API Resilience Tests

Verify fallback strategies during API failures:

```python
# Test API failure handling
from unittest.mock import AsyncMock, patch

async def test_api_failure():
    with patch('core.trade_executor.PolymarketClient') as mock_client:
        # Mock API to fail
        mock_client.return_value.place_order = AsyncMock(
            side_effect=APIError("API timeout", status_code=504)
        )

        # Should handle gracefully
        result = await executor.execute_copy_trade(trade_data)

        # Result should indicate error
        assert result["status"] == "error"
        assert result["error"] is not None
```

Tests verify:
- API timeouts are handled
- Fallback RPC endpoints are tried
- Circuit breaker isn't triggered by transient errors
- Retries work correctly

### Thread Safety Tests

Verify `asyncio.Lock` prevents race conditions:

```python
# Test concurrent access
import asyncio

async def concurrent_test():
    lock = asyncio.Lock()
    counter = 0

    async def increment():
        nonlocal counter
        async with lock:
            counter += 1

    # Run 100 concurrent increments
    tasks = [increment() for _ in range(100)]
    await asyncio.gather(*tasks)

    # Should be exactly 100
    assert counter == 100
```

Tests verify:
- Multiple concurrent operations don't corrupt state
- Lock acquisition timeout works
- Deadlocks don't occur
- State consistency is maintained

## Configuration Options

### TestingConfig

```python
from config.mcp_config import TestingConfig, get_testing_config

# Get configuration
config = get_testing_config()

# Access configuration
print(f"Enabled: {config.enabled}")
print(f"Coverage Target: {config.coverage_target:.1%}")
print(f"Max Duration: {config.max_test_duration_seconds}s")
print(f"Max Memory: {config.max_memory_gb}GB")
print(f"Max CPU Cores: {config.max_cpu_cores}")
print(f"Critical Modules: {config.critical_modules}")
```

### Environment Variables

Set in `.env` file:

```bash
# Enable/disable testing server
TESTING_SERVER_ENABLED=true

# Set coverage target
COVERAGE_TARGET=0.85

# Run on commit/PR
RUN_ON_COMMIT=true
RUN_ON_PR=true

# Alert on coverage drop
ALERT_ON_COVERAGE_DROP=true
```

## Integration with Existing Systems

### 1. Main.py Integration

Add to `PolymarketCopyBot.__init__()`:

```python
from mcp.testing_server import get_testing_server

class PolymarketCopyBot:
    def __init__(self) -> None:
        # ... existing initialization ...

        # Initialize testing server
        self.testing_server = get_testing_server()
```

Add to `shutdown()` method:

```python
async def shutdown(self):
    # ... existing shutdown code ...

    # Shutdown testing server
    if self.testing_server:
        await self.testing_server.shutdown()
        logger.info("✅ Testing server stopped")
```

### 2. Monitoring Dashboard Integration

Add test results endpoint to existing monitoring:

```python
# In your FastAPI app
from fastapi import FastAPI
from mcp.testing_server import get_testing_server

app = FastAPI()
testing_server = get_testing_server()

@app.get("/api/test-results")
async def get_test_results():
    """Get real-time test results."""
    dashboard = await testing_server.get_test_dashboard_data()
    return dashboard

@app.get("/api/test/coverage")
async def get_coverage_report():
    """Get detailed coverage report."""
    return testing_server.coverage_cache.get_stats()
```

### 3. Telegram Alert Integration

Test failures already integrate with existing alerts:

```python
# Automatic notification on test failures
# Uses existing send_telegram_alert() from utils/alerts.py
```

Alerts include:
- Test failure notifications
- Coverage drop warnings
- Circuit breaker status changes
- Performance degradation alerts

## Troubleshooting

### Circuit Breaker Active

If you see "Testing circuit breaker is open" errors:

1. **Wait for cooldown** (default 5 minutes)
2. **Check recent failures**: Review why tests are failing
3. **Fix issues**: Address root causes of failures
4. **Manual reset**: If issues are resolved, reset circuit breaker

### Coverage Drop Alert

If you see coverage drop alerts:

1. **Run tests locally**: `pytest tests/ --cov=. --cov-report=term-missing`
2. **Review missing coverage**: Identify untested code paths
3. **Add tests**: Cover missing lines/branches
4. **Verify threshold**: Ensure target (85%) is realistic

### Test Timeout

If tests timeout:

1. **Increase timeout**: Adjust `max_test_duration_seconds` in config
2. **Optimize tests**: Remove unnecessary delays, mock slow operations
3. **Check for infinite loops**: Review test logic
4. **Profile performance**: Identify bottlenecks

### Memory Issues

If tests exceed memory limits:

1. **Review test fixtures**: Ensure fixtures don't leak memory
2. **Check test data**: Use smaller datasets for testing
3. **Verify cleanup**: Ensure tests clean up resources
4. **Increase limit**: Adjust `max_memory_gb` if needed

### Pre-Commit Hooks Failing

If pre-commit hooks fail:

1. **Run manually**: `pre-commit run --all-files`
2. **Check specific hook**: Run individual hook to see errors
3. **Fix issues**: Address linting, type checking, or test failures
4. **Bypass if needed**: Use `git commit --no-verify` (not recommended)

### GitHub Actions Failures

If CI/CD tests fail:

1. **Check logs**: Review GitHub Actions logs
2. **Download artifacts**: View coverage reports and benchmark results
3. **Reproduce locally**: Run same tests to reproduce failures
4. **Fix and push**: Address issues and push new commit

## Performance Benchmarks

### Expected Performance

Based on typical test suite:

| Operation | Expected Time |
|-----------|---------------|
| Single test | <100ms |
| Test file (100 tests) | <5s |
| Coverage report | <2s |
| Full critical suite | <30s |
| Dashboard data | <50ms |

### Coverage Targets

Minimum coverage targets:

| Module | Target | Current |
|---------|--------|---------|
| `core.trade_executor` | 90% | TBD |
| `core.circuit_breaker` | 95% | TBD |
| `scanners.market_analyzer` | 85% | TBD |
| `core.wallet_monitor` | 85% | TBD |

Run coverage report:

```bash
pytest tests/ --cov=. --cov-report=html
# View: open htmlcov/index.html
```

## Automatic Test Generation

### Endgame Sweeper Tests

Generate tests for endgame strategy risk parameters:

```python
from mcp.testing_server import get_testing_server

async def generate():
    server = get_testing_server()
    test_file = await server.generate_tests_for_strategy("endgame_sweeper")
    print(f"Generated: {test_file}")

asyncio.run(generate())
```

Generated tests include:
- Minimum probability threshold (0.95)
- Maximum probability exit (0.998)
- Position size limits (3%)
- Stop loss percentage (10%)
- Minimum annualized return (20%)
- Liquidity thresholds ($10,000)

### Quality Whale Copy Tests

Generate tests for whale wallet filtering:

```python
async def generate():
    server = get_testing_server()
    test_file = await server.generate_tests_for_strategy("quality_whale")
    print(f"Generated: {test_file}")

asyncio.run(generate())
```

Generated tests include:
- Minimum confidence score
- Maximum risk score
- Minimum trade volume
- Position size factor bounds

### Cross-Market Arbitrage Tests

Generate tests for arbitrage logic:

```python
async def generate():
    server = get_testing_server()
    test_file = await server.generate_tests_for_strategy("cross_market_arbitrage")
    print(f"Generated: {test_file}")

asyncio.run(generate())
```

Generated tests include:
- High correlation threshold (0.9)
- Minimum spread percentage
- Maximum position size for arbitrage

## Testing Best Practices

### 1. DO NOT Use Real API Keys

Tests must mock all external API calls:

```python
# ✅ CORRECT
from unittest.mock import AsyncMock

mock_client = AsyncMock()
mock_client.place_order = AsyncMock(return_value={"order_id": "123"})

# ❌ WRONG - Never use real keys
client = PolymarketClient(api_key="real_key")  # Don't commit!
```

### 2. DO NOT Modify Risk Parameters

Tests must NOT change production risk settings:

```python
# ✅ CORRECT
# Test with mock settings
test_settings = Settings(max_daily_loss=100.0)

# ❌ WRONG - Never modify real settings
settings.max_daily_loss = 999999.0  # Don't do this!
```

### 3. DO NOT Change Position Sizing

Tests must verify, not modify, position sizing logic:

```python
# ✅ CORRECT
# Verify position size calculation
assert position_size == expected_size

# ❌ WRONG - Never change calculation logic
position_size = Decimal("999999.0")  # Don't modify!
```

### 4. Use Test Data, Not Production Data

Tests must use isolated test data:

```python
# ✅ CORRECT
# Use fixtures with test data
def test_with_sample_data(sample_trade_data):
    result = execute_trade(sample_trade_data)
    assert result["status"] == "success"

# ❌ WRONG - Never use production data
real_wallet_transactions = get_from_database()  # Don't use!
```

### 5. Maintain Async/Await Patterns

All test operations must use async/await:

```python
# ✅ CORRECT
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None

# ❌ WRONG - Don't use sync in async tests
@pytest.mark.asyncio
async def test_sync_operation():
    result = sync_function()  # Missing await!
    assert result is not None
```

## Testing Strategies

### Strategy 1: Incremental Testing

Test small changes frequently:

```bash
# Run tests after each small change
pytest tests/unit/test_trade_executor.py -v

# Commit only if tests pass
git commit -m "Add new feature (tests passing)"
```

### Strategy 2: Test-Driven Development

Write tests before implementation:

```python
# 1. Write failing test
def test_new_feature():
    assert calculate_position(...) == expected

# 2. Run test (fails)
pytest tests/unit/test_feature.py -v  # FAILS

# 3. Implement feature
def calculate_position(...):
    # Implementation
    return result

# 4. Run test (passes)
pytest tests/unit/test_feature.py -v  # PASSES

# 5. Commit
git add tests/unit/test_feature.py core/calculations.py
git commit -m "Implement new feature with tests"
```

### Strategy 3: Regression Testing

After fixing bugs, add regression tests:

```python
# Test for specific bug that was fixed
def test_bug_fix_regression():
    """
    Regression test for bug #123:
    Ensure position size calculation handles edge cases correctly.
    """
    # Test the edge case that caused the bug
    account_balance = Decimal("0.0")
    risk_percent = Decimal("0.01")

    position_size = account_balance * risk_percent
    assert position_size == Decimal("0.0")
```

### Strategy 4: Property-Based Testing

Test invariants and properties:

```python
def test_position_size_non_negative():
    """Property: position size should never be negative."""
    account_balance = Decimal("10000.0")
    risk_percent = Decimal("0.01")

    position_size = account_balance * risk_percent
    assert position_size >= Decimal("0.0")

def test_position_size_does_not_exceed_max():
    """Property: position size never exceeds maximum."""
    max_position = Decimal("500.0")
    # Risk-based calculation would produce 5000.0
    position_size = min(risk_based, max_position)
    assert position_size <= max_position
```

## CI/CD Pipeline

### Pre-Commit Stage

Runs before each commit:

```yaml
# .pre-commit-config.yaml
- id: pytest-check
  name: Run Unit Tests
  entry: pytest
  types: [python]
  pass_filenames: ^tests/unit/.*\.py$
  args: [-xvs, --tb=short]
```

### Push Stage

Runs on every push to main/develop:

```yaml
# .github/workflows/test.yml
on:
  push:
    branches: [ main, develop ]

jobs:
  critical-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest tests/ --cov=.
```

### Pull Request Stage

Runs on every PR to main/develop:

```yaml
# .github/workflows/test.yml
on:
  pull_request:
    branches: [ main, develop ]

jobs:
  critical-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest tests/ --cov=.
```

### Post-Merge Stage

Runs after successful merge:

```yaml
# .github/workflows/test.yml
jobs:
  coverage-report:
    needs: [critical-tests]
    runs-on: ubuntu-latest
    steps:
      - name: Generate coverage report
        run: |
          coverage report --rcfile=.coveragerc
      - name: Check threshold
        run: |
          # Fail if coverage < 85%
          COVERAGE=$(coverage report | grep TOTAL | awk '{print $4}')
          if [ $COVERAGE -lt 85 ]; then
            echo "Coverage below target"
            exit 1
          fi
```

## Monitoring & Alerts

### Telegram Notifications

Automatic alerts for:

- **Test Failures**: Immediate notification on any test failure
- **Coverage Drops**: Warning when coverage falls below 85%
- **Circuit Breaker**: Alert when testing circuit breaker opens
- **Performance Issues**: Warning when tests take too long

### Dashboard Metrics

Real-time metrics available:

- Total tests run
- Success rate percentage
- Circuit breaker state
- Last coverage drop time
- Cache statistics
- Memory usage estimates

Access dashboard:

```python
from mcp.testing_server import get_testing_server

server = get_testing_server()
dashboard = await server.get_test_dashboard_data()
print(json.dumps(dashboard, indent=2))
```

## Safety Features

### 1. Circuit Breaker Protection

Prevents test execution during excessive failures:

- **Failure Threshold**: 5 consecutive failures
- **Cooldown Period**: 5 minutes (300 seconds)
- **Automatic Recovery**: Opens/closes based on failure patterns
- **State Persistence**: Maintains state across restarts

### 2. Resource Limits

Enforces resource usage limits:

- **Max Memory**: 2 GB per test run
- **Max CPU**: 4 cores per test run
- **Max Duration**: 5 minutes (300 seconds) per test
- **Timeout Enforcement**: Automatic kill after timeout

### 3. Test Data Isolation

Never uses production data:

- **Mock Databases**: All database calls are mocked
- **Test Fixtures**: Use fixtures with test data
- **Environment**: Separate test environment variables
- **Cleanup**: Clean up test data after execution

### 4. Fallback to Last Known Good

On test failures, system continues:

- **Circuit Breaker**: Opens after failures, allows manual reset
- **Graceful Degradation**: Tests failing don't crash the system
- **Partial Execution**: Some tests can fail without stopping all testing

## Critical Constraints

### ✅ DO NOT Use Real API Keys

All tests must mock external API calls. Never commit real keys:

```python
# ✅ CORRECT
from unittest.mock import AsyncMock

mock_api = AsyncMock()
mock_api.get_token_balance = AsyncMock(return_value=Decimal("10000.0"))

# ❌ WRONG - Never use real keys in tests
api = PolymarketClient(api_key="real_key")  # Don't commit!
```

### ✅ DO NOT Modify Risk Parameters

Tests verify but don't change risk management settings:

```python
# ✅ CORRECT
def test_circuit_breaker_threshold():
    assert settings.risk.max_daily_loss == 100.0

# ❌ WRONG - Never modify risk parameters
settings.risk.max_daily_loss = 999999.0  # Don't do this!
```

### ✅ DO NOT Change Position Sizing Logic

Tests verify position sizing, don't modify the logic:

```python
# ✅ CORRECT
def test_position_size_calculation():
    result = calculate_position(balance, risk)
    assert result == expected

# ❌ WRONG - Never modify calculation logic
def calculate_position(balance, risk):
    return Decimal("999999.0")  # Don't modify!
```

### ✅ Preserve All Existing Logging

Uses existing logger from `utils/logger.py`:

```python
# ✅ CORRECT
from utils.logger import get_logger

logger = get_logger(__name__)
logger.info("Test passed")

# ❌ WRONG - Don't create new loggers
import logging  # Don't do this!
logger = logging.getLogger(__name__)
```

### ✅ Maintain Async/Await Patterns

All test functions use async/await:

```python
# ✅ CORRECT
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None

# ❌ WRONG - Missing await
@pytest.mark.asyncio
async def test_async_function():
    result = async_function()  # Missing await!
    assert result is not None
```

## Quick Reference

### Common Commands

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing

# Run specific module
pytest tests/unit/test_trade_executor.py -v

# Run fast tests only
pytest tests/ -m "not slow"

# Generate coverage HTML report
pytest tests/ --cov=. --cov-report=html

# Install pre-commit hooks
pre-commit install

# Run pre-commit manually
pre-commit run --all-files

# Check for API keys in code
git diff --cached --name-only | xargs grep -l "PRIVATE_KEY\|API_KEY"

# Run tests with timeout
pytest tests/ --timeout=120
```

### Environment Variables

```bash
# Testing server
export TESTING_SERVER_ENABLED=true
export COVERAGE_TARGET=0.85
export RUN_ON_COMMIT=true
export RUN_ON_PR=true
export ALERT_ON_COVERAGE_DROP=true

# Telegram alerts (use existing)
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id
```

## Support

For issues or questions:

1. Check logs in `logs/` directory
2. Run health check: `pytest tests/ --collect-only`
3. Review circuit breaker state
4. Check coverage reports
5. Verify Ruff and MyPy installation

## License

MIT License - See project root for details.
