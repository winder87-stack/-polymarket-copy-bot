# Polymarket Copy Trading Bot - Test Suite

A comprehensive test suite for the Polymarket Copy Trading Bot covering unit tests, integration tests, security tests, performance tests, and edge case scenarios.

## 🧪 Test Coverage Overview

- **Unit Tests**: 90%+ code coverage for individual components
- **Integration Tests**: End-to-end trade flow and error recovery
- **Security Tests**: Input validation and exploit prevention
- **Performance Tests**: Load testing and latency measurement
- **Edge Case Tests**: Blockchain reorgs and network partitions

## 📁 Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests
│   ├── test_settings.py     # Configuration validation
│   ├── test_clob_client.py  # CLOB API interactions
│   ├── test_wallet_monitor.py # Wallet monitoring
│   ├── test_trade_executor.py # Trade execution & risk management
│   ├── test_security.py     # Data masking & validation
│   └── test_helpers.py      # Utility functions
├── integration/             # Integration tests
│   ├── test_end_to_end.py   # End-to-end trading flows
│   └── test_security_integration.py # Security integration
├── performance/             # Performance tests
│   └── test_performance.py  # Load & latency testing
├── mocks/                   # Mock implementations
│   ├── __init__.py
│   ├── polygonscan_mock.py  # PolygonScan API mock
│   ├── clob_api_mock.py     # CLOB API mock
│   └── web3_mock.py         # Web3 provider mock
└── README.md               # This file
```

## 🚀 Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov pytest-xdist pytest-html

# For development
pip install pytest-watch black isort flake8 mypy
```

### Run All Tests

```bash
# Run complete test suite
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m performance   # Performance tests only
pytest -m security      # Security tests only
```

### Development Workflow

```bash
# Run tests in watch mode (reruns on file changes)
pytest-watch

# Run tests with detailed output
pytest -v

# Run specific test file
pytest tests/unit/test_settings.py

# Run specific test class
pytest tests/unit/test_settings.py::TestSettings

# Run specific test method
pytest tests/unit/test_settings.py::TestSettings::test_settings_initialization
```

## 🧩 Test Categories

### Unit Tests (`tests/unit/`)

Focused tests for individual components with comprehensive mocking.

#### `test_settings.py`
- Configuration validation and loading
- Environment variable parsing
- Critical settings validation
- Wallet configuration handling

#### `test_clob_client.py`
- CLOB API interactions
- Order placement and cancellation
- Market data retrieval
- Error handling and retries
- Gas price optimization
- Slippage protection

#### `test_wallet_monitor.py`
- Transaction detection and parsing
- Wallet monitoring logic
- Rate limiting and throttling
- Polymarket trade identification
- Confidence scoring

#### `test_trade_executor.py`
- Trade execution logic
- Risk management rules
- Position sizing calculations
- Circuit breaker functionality
- Stop loss and take profit
- Performance tracking

#### `test_security.py`
- Private key validation
- Sensitive data masking
- Secure logging
- Session ID generation
- Secure string comparison

#### `test_helpers.py`
- Address normalization
- Currency conversion
- Confidence score calculation
- Position sizing utilities
- Time formatting
- JSON parsing

### Integration Tests (`tests/integration/`)

End-to-end tests that verify component interactions.

#### `test_end_to_end.py`
- Complete trading cycle
- Error recovery scenarios
- Circuit breaker integration
- Performance reporting
- Concurrent operations

#### `test_security_integration.py`
- Input validation security
- SQL injection prevention
- XSS attack prevention
- Rate limiting bypass prevention
- Unauthorized access prevention

### Performance Tests (`tests/performance/`)

Load testing and performance validation.

#### `test_performance.py`
- 25-wallet monitoring load test
- High-frequency transaction processing
- Concurrent trade execution
- Memory usage profiling
- API rate limit stress testing
- Scalability testing

### Edge Case Tests (`tests/integration/test_edge_cases.py`)

Handling of extreme and unusual conditions.

- **Blockchain Reorgs**: Transaction disappearance simulation
- **Network Partitions**: Connection failures and recovery
- **Invalid Transactions**: Malformed data handling
- **Clock Skew**: Timestamp inconsistencies
- **Extreme Values**: Maximum/minimum value handling
- **Concurrency Issues**: Race condition prevention

## 🎭 Mock Implementations

### PolygonScan API Mock (`tests/mocks/polygonscan_mock.py`)
```python
from tests.mocks.polygonscan_mock import PolygonScanMockServer

# Start mock server
server = PolygonScanMockServer()
await server.start()

# Use in tests
client = AsyncPolygonScanClient()
transactions = await client.get_transactions(wallet_address)
```

### CLOB API Mock (`tests/mocks/clob_api_mock.py`)
```python
from tests.mocks.clob_api_mock import CLOBAPIMock, MockCLOBClient

# Create mock API
api = CLOBAPIMock()
api.set_balance(wallet_address, 1000.0)

# Create client
client = MockCLOBClient(api)
balance = client.get_balance()
```

### Web3 Provider Mock (`tests/mocks/web3_mock.py`)
```python
from tests.mocks.web3_mock import create_mock_web3

# Create mock Web3
web3 = create_mock_web3()
block_number = web3.eth.block_number
balance = web3.eth.get_balance(address)
```

## 📊 Test Configuration

### Pytest Configuration (`pytest.ini`)

```ini
[tool:pytest]
testpaths = tests
addopts =
    --verbose
    --tb=short
    --cov=.
    --cov-report=html:htmlcov
    --cov-report=term-missing
    --cov-fail-under=90
    --asyncio-mode=auto

markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    security: Security tests
    slow: Slow running tests
```

### Coverage Requirements

- **Minimum Coverage**: 90% overall
- **Critical Paths**: 95%+ coverage
- **Security Functions**: 100% coverage

## 🔧 Test Fixtures (`conftest.py`)

### Shared Fixtures

- `event_loop`: Asyncio event loop
- `test_settings`: Application settings
- `mock_polymarket_client`: Mocked CLOB client
- `mock_wallet_monitor`: Mocked wallet monitor
- `mock_trade_executor`: Mocked trade executor
- `sample_trade`: Sample trade data
- `sample_market_data`: Sample market data
- `sample_transaction`: Sample blockchain transaction

### Performance Fixtures

- `performance_monitor`: Performance measurement
- `performance_test_data`: Load testing data

### Security Fixtures

- `security_test_payloads`: Security test payloads
- `edge_case_scenarios`: Edge case test data

## 🚦 CI/CD Pipeline (`.github/workflows/ci.yml`)

### Pipeline Stages

1. **Test**: Unit tests with coverage
2. **Integration**: End-to-end testing
3. **Performance**: Load and latency testing
4. **Security**: Vulnerability scanning
5. **Docker**: Container build verification
6. **Deploy**: Automated deployment

### Quality Gates

- ✅ Test coverage > 90%
- ✅ All tests passing
- ✅ No security vulnerabilities
- ✅ Code quality checks passing
- ✅ Performance benchmarks met

## 📈 Running Tests

### Local Development

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific categories
pytest -m "unit and not slow"
pytest -m integration
pytest -m performance

# Run tests in parallel
pytest -n auto

# Generate HTML report
pytest --html=report.html
```

### CI/CD Execution

```bash
# Unit tests with coverage
pytest tests/unit/ -v --cov=. --cov-report=xml

# Integration tests
pytest tests/integration/ -v

# Performance tests (subset for CI)
pytest tests/performance/ -k "not load" -v

# Security tests
pytest tests/integration/test_security_integration.py -v
```

### Performance Testing

```bash
# Full performance suite (long running)
pytest tests/performance/ -v --durations=10

# Load testing (resource intensive)
pytest tests/performance/test_performance.py::TestLoadTesting -v

# Memory profiling
pytest tests/performance/ -k memory -v
```

## 🔍 Test Data Generation

### Test Data Utilities

```python
# Generate realistic test data
from tests.conftest import sample_trade, sample_market_data

# Create custom test scenarios
custom_trade = sample_trade.copy()
custom_trade['amount'] = 50.0
custom_trade['side'] = 'SELL'
```

### Mock Data Factories

```python
from tests.mocks.clob_api_mock import create_clob_api_with_custom_data
from tests.mocks.web3_mock import create_web3_with_custom_state

# Create API with custom market data
api = create_clob_api_with_custom_data(markets=custom_markets)

# Create Web3 with custom balances
web3 = create_web3_with_custom_state(balances=custom_balances)
```

## 🐛 Debugging Tests

### Common Issues

1. **Async Test Failures**
   ```python
   # Ensure proper async fixture usage
   @pytest.mark.asyncio
   async def test_async_function(self, mock_client):
       result = await mock_client.async_method()
       assert result is not None
   ```

2. **Mock Configuration**
   ```python
   # Properly configure mocks
   mock_client.return_value.get_balance.return_value = 1000.0
   mock_client.get_balance.assert_called_once()
   ```

3. **Fixture Dependencies**
   ```python
   # Ensure fixture dependencies are correct
   async def test_with_dependencies(self, mock_polymarket_client, test_settings):
       assert mock_polymarket_client.settings == test_settings
   ```

### Debugging Commands

```bash
# Run with detailed output
pytest -v -s --tb=long

# Run single failing test
pytest tests/unit/test_settings.py::TestSettings::test_invalid_private_key -v

# Run with debugger
pytest --pdb

# Profile test performance
pytest --durations=10
```

## 📋 Test Maintenance

### Adding New Tests

1. **Unit Tests**: Add to appropriate `tests/unit/test_*.py`
2. **Integration Tests**: Add to `tests/integration/`
3. **Performance Tests**: Add to `tests/performance/`
4. **Security Tests**: Add to `tests/integration/test_security_integration.py`

### Updating Fixtures

- Update `conftest.py` for shared fixtures
- Update mock implementations in `tests/mocks/`
- Ensure backward compatibility

### Coverage Requirements

- Maintain 90%+ overall coverage
- Critical security functions: 100%
- Trading logic: 95%+
- Error handling paths: Complete coverage

## 🔒 Security Testing

### Security Test Categories

- **Input Validation**: SQL injection, XSS, path traversal
- **Authentication**: Private key validation, session security
- **Data Protection**: Sensitive data masking, secure logging
- **Rate Limiting**: API abuse prevention
- **Circuit Breakers**: Failure mode protection

### Security Testing Tools

```bash
# Bandit security linting
bandit -r . -f json

# Safety vulnerability checking
safety check

# Custom security tests
pytest tests/integration/test_security_integration.py -v
```

## 📊 Performance Benchmarks

### Target Performance Metrics

- **API Latency**: < 200ms average response time
- **Transaction Processing**: < 100ms per transaction
- **Memory Usage**: < 50MB increase under load
- **Concurrent Operations**: Support 25+ wallet monitoring
- **Error Recovery**: < 5 seconds recovery time

### Performance Testing Commands

```bash
# Load testing
pytest tests/performance/test_performance.py::TestLoadTesting -v

# Latency measurement
pytest tests/performance/test_performance.py::TestLatencyMeasurement -v

# Memory profiling
pytest tests/performance/test_performance.py -k memory -v
```

## 🚨 Troubleshooting

### Common Test Failures

1. **Import Errors**: Check Python path and dependencies
2. **Async Test Issues**: Ensure proper event loop configuration
3. **Mock Failures**: Verify mock setup and assertions
4. **Coverage Issues**: Check source file inclusion/exclusion

### Getting Help

1. Check existing test patterns in the codebase
2. Review `conftest.py` for fixture examples
3. Run tests with `-v -s` for detailed output
4. Check CI/CD logs for environment differences

## 📚 Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [AsyncIO Testing](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [Web3.py Testing](https://web3py.readthedocs.io/en/stable/examples.html#testing)

---

## 🎯 Test Execution Summary

```bash
# Complete test suite execution
pytest --cov=. --cov-report=html --cov-report=term-missing

# Results will show:
# - Test pass/fail status
# - Code coverage percentage
# - Performance metrics
# - Security test results
```

**Happy Testing! 🧪**
