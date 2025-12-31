# Testing Strategy

## Overview

This document outlines the comprehensive testing strategy for the Polymarket Copy Trading Bot, focusing on achieving 90%+ code coverage with emphasis on high-risk modules.

## Testing Philosophy

1. **Security First**: All security-critical code must have comprehensive tests
2. **Edge Case Coverage**: Focus on edge cases and error conditions
3. **Realistic Scenarios**: Use realistic market data generators
4. **Parameterized Tests**: Use pytest parameterization for comprehensive coverage
5. **CI Integration**: Automated coverage checks block PRs with coverage drops

## Test Structure

```
tests/
├── fixtures/
│   └── market_data_generators.py    # Test data generators
├── unit/                             # Unit tests
│   ├── test_position_sizing_edge_cases.py
│   ├── test_circuit_breaker_state_transitions.py
│   ├── test_transaction_monitor_rate_limiting.py
│   ├── test_trade_executor_slippage.py
│   └── test_validation_security.py
├── integration/                      # Integration tests
└── conftest.py                       # Shared fixtures
```

## High-Risk Modules

### 1. Position Sizing (`utils/helpers.py`, `core/trade_executor.py`)

**Risk Level**: CRITICAL
**Coverage Target**: 95%+

**Test Focus**:
- Volatile market conditions
- Extreme price movements
- Low liquidity scenarios
- Edge cases (zero balance, very large amounts)
- Precision handling with Decimal
- Market crash/surge scenarios

**Key Test Cases**:
- Position sizing with different volatility levels
- Price movement impact on position size
- Low liquidity position sizing
- Edge cases (minimum/maximum values)
- Precision and rounding behavior

### 2. Circuit Breaker (`core/circuit_breaker.py`)

**Risk Level**: CRITICAL
**Coverage Target**: 95%+

**Test Focus**:
- State transition logic
- Activation conditions (daily loss, consecutive losses, failure rate)
- Auto-reset after cooldown
- Daily loss reset at midnight UTC
- State persistence
- Thread safety

**Key Test Cases**:
- Daily loss activation
- Consecutive losses activation
- Failure rate activation
- Profit resets consecutive losses
- Auto-reset after cooldown
- Daily loss reset at midnight
- Manual reset
- State persistence across restarts
- Concurrent state access

### 3. Transaction Monitor Rate Limiting (`utils/rate_limited_client.py`, `core/wallet_monitor.py`)

**Risk Level**: HIGH
**Coverage Target**: 90%+

**Test Focus**:
- Rate limit enforcement
- Error recovery mechanisms
- Concurrent request handling
- Exponential backoff
- Network error handling
- Timeout handling

**Key Test Cases**:
- Rate limit enforcement
- Concurrent rate limiting
- Rate limit error handling
- Exponential backoff on rate limits
- Network error recovery
- Timeout error recovery
- Partial failure recovery
- Circuit breaker on repeated errors

### 4. Trade Executor Slippage Protection (`core/trade_executor.py`)

**Risk Level**: HIGH
**Coverage Target**: 90%+

**Test Focus**:
- Slippage detection
- Slippage protection mechanisms
- Volatile market slippage
- Low liquidity slippage
- Edge cases

**Key Test Cases**:
- Slippage detection
- Slippage within limits
- Extreme slippage rejection
- Slippage with volatile markets
- Slippage edge cases
- Slippage with low liquidity
- Slippage with balance changes

### 5. Validation Security (`utils/validation.py`)

**Risk Level**: CRITICAL
**Coverage Target**: 95%+

**Test Focus**:
- Private key validation
- Wallet address validation
- Input sanitization
- Malicious input detection
- Security edge cases

**Key Test Cases**:
- Private key format validation
- Private key length validation
- Wallet address validation
- Checksum validation
- Input sanitization
- Malicious input detection
- Trade amount security
- Price security
- Transaction data security
- Config security

## Test Data Generators

### MarketDataGenerator

Generates realistic market test data:
- `generate_volatile_price_series()`: Price series with volatility
- `generate_slippage_scenario()`: Slippage scenarios
- `generate_trade_data()`: Trade data with edge cases
- `generate_market_conditions()`: Market conditions (low/normal/high/extreme volatility)
- `generate_account_balance_scenarios()`: Various balance scenarios
- `generate_position_size_inputs()`: Position size calculation inputs

### CircuitBreakerScenarioGenerator

Generates circuit breaker test scenarios:
- `generate_state_transition_scenarios()`: State transition scenarios

### ValidationTestDataGenerator

Generates validation test data:
- `generate_wallet_addresses()`: Wallet address test cases
- `generate_private_keys()`: Private key test cases
- `generate_malicious_inputs()`: Malicious input test cases

## Parameterized Testing

Use pytest parameterization for comprehensive coverage:

```python
@pytest.mark.parametrize("volatility_level,expected_range", [
    ("low", (0.45, 0.55)),
    ("normal", (0.40, 0.60)),
    ("high", (0.30, 0.70)),
    ("extreme", (0.10, 0.90)),
])
def test_position_size_with_volatility(volatility_level, expected_range):
    # Test implementation
    pass
```

## Coverage Requirements

### Overall Coverage
- **Minimum**: 90%
- **Target**: 95%+
- **Critical Modules**: 95%+

### Coverage Exclusions
- Test files themselves
- `__main__` blocks
- Debug code
- Protocol classes
- Abstract methods

### Coverage Reporting
- HTML report: `htmlcov/index.html`
- XML report: `coverage.xml`
- Terminal report: `--cov-report=term-missing`

## CI Pipeline Integration

### GitHub Actions Workflow

The CI pipeline (`/.github/workflows/test-coverage.yml`) performs:

1. **Test Execution**: Runs all tests with coverage
2. **Coverage Check**: Verifies coverage meets 90% threshold
3. **Coverage Upload**: Uploads to Codecov
4. **PR Comments**: Comments on PRs with coverage changes

### Coverage Threshold Enforcement

- **PR Blocking**: PRs with coverage below 90% are blocked
- **Coverage Drop Detection**: Coverage drops trigger warnings
- **Minimum Thresholds**:
  - Overall: 90%
  - Critical modules: 95%

## Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run with Coverage
```bash
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing
```

### Run Specific Test File
```bash
pytest tests/unit/test_position_sizing_edge_cases.py -v
```

### Run with Coverage Threshold
```bash
pytest tests/ --cov=. --cov-fail-under=90
```

### Run Parameterized Tests
```bash
pytest tests/unit/test_position_sizing_edge_cases.py::TestPositionSizingVolatileMarkets::test_position_size_with_volatility -v
```

## Test Maintenance

### Adding New Tests

1. **Identify Coverage Gap**: Use coverage report to find untested code
2. **Write Test**: Follow existing test patterns
3. **Use Generators**: Use test data generators for realistic scenarios
4. **Parameterize**: Use parameterization for comprehensive coverage
5. **Verify Coverage**: Run coverage report to verify improvement

### Updating Tests

1. **Update Generators**: Update test data generators when adding new scenarios
2. **Maintain Coverage**: Ensure coverage doesn't drop below threshold
3. **Update Documentation**: Update this document when adding new test patterns

## Best Practices

1. **Test Edge Cases**: Always test boundary conditions
2. **Use Fixtures**: Use pytest fixtures for common setup
3. **Mock External Dependencies**: Mock external APIs and services
4. **Test Error Paths**: Test error handling and recovery
5. **Test Concurrency**: Test thread-safe code with concurrent operations
6. **Use Realistic Data**: Use test data generators for realistic scenarios
7. **Document Test Intent**: Use descriptive test names and docstrings

## Metrics and Monitoring

### Coverage Metrics
- Overall coverage percentage
- Per-module coverage
- Line coverage
- Branch coverage

### Test Metrics
- Number of tests
- Test execution time
- Test failure rate
- Flaky test detection

### Quality Metrics
- Code complexity
- Test quality score
- Security test coverage

## Continuous Improvement

1. **Regular Reviews**: Review test coverage reports regularly
2. **Gap Analysis**: Identify and fill coverage gaps
3. **Refactoring**: Refactor tests for maintainability
4. **Performance**: Optimize slow tests
5. **Documentation**: Keep testing strategy up to date

## References

- [pytest Documentation](https://docs.pytest.org/)
- [coverage.py Documentation](https://coverage.readthedocs.io/)
- [Codecov Documentation](https://docs.codecov.com/)
