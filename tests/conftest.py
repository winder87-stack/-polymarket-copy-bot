"""
Test configuration and fixtures for Polymarket Copy Trading Bot tests.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import os
import tempfile
import shutil
from decimal import Decimal

# Import the application modules
from config.settings import Settings, RiskManagementConfig, NetworkConfig, TradingConfig, MonitoringConfig, AlertingConfig, LoggingConfig
from core.clob_client import PolymarketClient
from core.wallet_monitor import WalletMonitor
from core.trade_executor import TradeExecutor
from utils.helpers import normalize_address, calculate_confidence_score
from utils.security import secure_log, validate_private_key


# Test constants
TEST_PRIVATE_KEY = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
TEST_WALLET_ADDRESS = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
TEST_CONDITION_ID = "0x1234567890abcdef1234567890abcdef12345678"
TEST_TOKEN_ID = "0xabcdef1234567890abcdef1234567890abcdef12"
TEST_TARGET_WALLETS = [
    "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    "0x742d35Cc6634C0532925a3b844Bc454e4438f44f",
    "0x742d35Cc6634C0532925a3b844Bc454e4438f450"
]


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_private_key():
    """Test private key for unit tests."""
    return TEST_PRIVATE_KEY


@pytest.fixture(scope="session")
def test_wallet_address():
    """Test wallet address."""
    return TEST_WALLET_ADDRESS


@pytest.fixture(scope="session")
def test_condition_id():
    """Test condition ID."""
    return TEST_CONDITION_ID


@pytest.fixture(scope="session")
def test_token_id():
    """Test token ID."""
    return TEST_TOKEN_ID


@pytest.fixture(scope="session")
def test_target_wallets():
    """List of test target wallets."""
    return TEST_TARGET_WALLETS


@pytest.fixture
def sample_trade():
    """Sample trade data for testing."""
    return {
        'tx_hash': '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
        'timestamp': datetime.now() - timedelta(seconds=30),
        'block_number': 50000000,
        'wallet_address': TEST_WALLET_ADDRESS,
        'contract_address': '0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a',
        'value_eth': 0.0,
        'gas_used': 150000,
        'gas_price': 50000000000,
        'input_data': '0x1234567890abcdef',
        'condition_id': TEST_CONDITION_ID,
        'market_id': 'unknown',
        'outcome_index': 0,
        'side': 'BUY',
        'amount': 10.0,
        'price': 0.65,
        'token_id': TEST_TOKEN_ID,
        'confidence_score': 0.8
    }


@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    return {
        'conditionId': TEST_CONDITION_ID,
        'tokens': [
            {'tokenId': TEST_TOKEN_ID, 'outcome': 'YES'},
            {'tokenId': '0xabcdef1234567890abcdef1234567890abcdef13', 'outcome': 'NO'}
        ],
        'active': True,
        'closed': False,
        'question': 'Will ETH reach $5000 by end of 2024?',
        'description': 'Ethereum price prediction market'
    }


@pytest.fixture
def sample_order_book():
    """Sample order book data."""
    return {
        'bids': [
            {'price': '0.65', 'size': '100.0'},
            {'price': '0.64', 'size': '50.0'},
            {'price': '0.63', 'size': '75.0'}
        ],
        'asks': [
            {'price': '0.66', 'size': '80.0'},
            {'price': '0.67', 'size': '60.0'},
            {'price': '0.68', 'size': '40.0'}
        ]
    }


@pytest.fixture
def sample_transaction():
    """Sample Polygonscan transaction data."""
    return {
        'hash': '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
        'from': TEST_WALLET_ADDRESS,
        'to': '0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a',
        'value': '0',
        'gasUsed': '150000',
        'gasPrice': '50000000000',
        'timeStamp': str(int((datetime.now() - timedelta(seconds=30)).timestamp())),
        'input': '0x1234567890abcdef',
        'blockNumber': '50000000'
    }


@pytest.fixture
def mock_web3():
    """Mock Web3 provider."""
    mock_web3 = Mock()
    mock_web3.is_connected.return_value = True
    mock_web3.eth.block_number = 50000000
    mock_web3.eth.gas_price = 50000000000  # 50 gwei
    mock_web3.from_wei = lambda x, unit: x / 10**18 if unit == 'ether' else x / 10**9 if unit == 'gwei' else x
    mock_web3.to_checksum_address = lambda addr: addr
    return mock_web3


@pytest.fixture
def mock_clob_client():
    """Mock Polymarket CLOB client."""
    mock_client = Mock()
    mock_client.get_balance.return_value = 1000.0
    mock_client.get_market.return_value = {
        'conditionId': TEST_CONDITION_ID,
        'tokens': [{'tokenId': TEST_TOKEN_ID}],
        'active': True
    }
    mock_client.get_markets.return_value = [
        {'conditionId': TEST_CONDITION_ID, 'active': True},
        {'conditionId': '0xabcdef1234567890abcdef1234567890abcdef', 'active': True}
    ]
    mock_client.get_active_orders.return_value = []
    mock_client.get_order_book.return_value = {
        'bids': [{'price': '0.65', 'size': '100'}],
        'asks': [{'price': '0.66', 'size': '80'}]
    }
    mock_client.get_trades.return_value = []
    mock_client.create_order.return_value = {'orderId': 'test-order-123'}
    mock_client.post_order.return_value = {'orderID': 'test-order-123'}
    mock_client.cancel.return_value = True
    return mock_client


@pytest.fixture
def mock_polygonscan_response():
    """Mock Polygonscan API response."""
    return {
        'status': '1',
        'message': 'OK',
        'result': [
            {
                'hash': '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
                'from': TEST_WALLET_ADDRESS,
                'to': '0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a',
                'value': '0',
                'gasUsed': '150000',
                'gasPrice': '50000000000',
                'timeStamp': str(int((datetime.now() - timedelta(seconds=30)).timestamp())),
                'input': '0x1234567890abcdef',
                'blockNumber': '50000000'
            }
        ]
    }


@pytest.fixture
def mock_aiohttp_session(mock_polygonscan_response):
    """Mock aiohttp ClientSession."""
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_polygonscan_response)
    mock_session.get.return_value.__aenter__.return_value = mock_response
    return mock_session


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    config_data = {
        'target_wallets': TEST_TARGET_WALLETS,
        'min_confidence_score': 0.7
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        'PRIVATE_KEY': TEST_PRIVATE_KEY,
        'WALLET_ADDRESS': TEST_WALLET_ADDRESS,
        'POLYGON_RPC_URL': 'https://polygon-rpc.com',
        'POLYGONSCAN_API_KEY': 'test-api-key',
        'TELEGRAM_BOT_TOKEN': 'test-bot-token',
        'TELEGRAM_CHAT_ID': '123456789',
        'MAX_DAILY_LOSS': '100.0',
        'MAX_POSITION_SIZE': '50.0',
        'MONITOR_INTERVAL': '15'
    }

    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def test_settings(mock_env_vars):
    """Test settings instance."""
    return Settings()


@pytest.fixture
async def mock_polymarket_client(mock_web3, mock_clob_client):
    """Mock PolymarketClient instance."""
    with patch('core.clob_client.Web3', return_value=mock_web3), \
         patch('core.clob_client.ClobClient', return_value=mock_clob_client):

        client = PolymarketClient()
        yield client


@pytest.fixture
async def mock_wallet_monitor(mock_web3, test_settings):
    """Mock WalletMonitor instance."""
    with patch('core.wallet_monitor.Web3', return_value=mock_web3):
        monitor = WalletMonitor()
        yield monitor


@pytest.fixture
async def mock_trade_executor(mock_polymarket_client, test_settings):
    """Mock TradeExecutor instance."""
    executor = TradeExecutor(mock_polymarket_client)
    yield executor


@pytest.fixture
def mock_telegram_alert():
    """Mock telegram alert function."""
    return AsyncMock()


@pytest.fixture
def mock_send_error_alert():
    """Mock error alert function."""
    return AsyncMock()


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    logger = Mock()
    logger.info = Mock()
    logger.error = Mock()
    logger.warning = Mock()
    logger.debug = Mock()
    logger.critical = Mock()
    return logger


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Clear any cached instances
    from config.settings import settings
    # Force reload by clearing cached values
    if hasattr(settings, '_loaded_from_env'):
        delattr(settings, '_loaded_from_env')


@pytest.fixture
def performance_test_data():
    """Data for performance testing."""
    return {
        'wallets': [f"0x{'0'*39}{i:01x}" for i in range(25)],
        'transactions': [
            {
                'hash': f'0x{i:064x}',
                'from': f"0x{'0'*39}{i%25:01x}",
                'to': '0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a',
                'value': '0',
                'gasUsed': str(100000 + i * 1000),
                'gasPrice': str(30000000000 + i * 1000000000),
                'timeStamp': str(int((datetime.now() - timedelta(seconds=i*10)).timestamp())),
                'input': f'0x1234567890abcdef{i:016x}',
                'blockNumber': str(50000000 + i)
            } for i in range(1000)
        ]
    }


@pytest.fixture
def edge_case_scenarios():
    """Edge case test scenarios."""
    return {
        'blockchain_reorg': {
            'original_tx': {
                'hash': '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
                'blockNumber': '50000000'
            },
            'reorg_tx': {
                'hash': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
                'blockNumber': '50000001'  # Different block
            }
        },
        'network_partition': {
            'timeout_error': TimeoutError("Connection timeout"),
            'connection_error': ConnectionError("Network unreachable")
        },
        'invalid_transaction': {
            'missing_fields': {},
            'invalid_price': {'price': 1.5, 'amount': -10.0},
            'ancient_timestamp': {'timestamp': datetime.now() - timedelta(days=30)}
        },
        'clock_skew': {
            'future_timestamp': datetime.now() + timedelta(hours=1),
            'past_timestamp': datetime.now() - timedelta(days=1)
        }
    }


@pytest.fixture
def security_test_payloads():
    """Security test payloads for injection and validation testing."""
    return {
        'sql_injection': {
            'input': "'; DROP TABLE users; --",
            'expected_rejected': True
        },
        'xss_attempt': {
            'input': "<script>alert('xss')</script>",
            'expected_rejected': True
        },
        'path_traversal': {
            'input': "../../../etc/passwd",
            'expected_rejected': True
        },
        'large_input': {
            'input': 'A' * 1000000,  # 1MB string
            'expected_rejected': True
        },
        'negative_amount': {
            'amount': -100.0,
            'expected_rejected': True
        },
        'zero_price': {
            'price': 0.0,
            'expected_rejected': True
        },
        'invalid_address': {
            'address': 'invalid-address',
            'expected_rejected': True
        },
        'malformed_private_key': {
            'private_key': '0xinvalid',
            'expected_rejected': True
        }
    }


# Async test utilities
@pytest.fixture
def async_test_timeout():
    """Timeout for async tests."""
    return 30  # seconds


@pytest.fixture
def mock_async_sleep():
    """Mock asyncio.sleep for faster tests."""
    return AsyncMock()


# Performance monitoring fixtures
@pytest.fixture
def performance_monitor():
    """Performance monitoring fixture."""
    class PerformanceMonitor:
        def __init__(self):
            self.start_times = {}
            self.metrics = {}

        def start(self, name: str):
            self.start_times[name] = asyncio.get_event_loop().time()

        def end(self, name: str):
            if name in self.start_times:
                duration = asyncio.get_event_loop().time() - self.start_times[name]
                self.metrics[name] = duration
                return duration
            return 0

        def get_metrics(self):
            return self.metrics.copy()

    return PerformanceMonitor()


# Cleanup fixture for test isolation
@pytest.fixture(autouse=True)
def cleanup_test_artifacts():
    """Clean up test artifacts after each test."""
    yield
    # Add cleanup logic here if needed
    pass
