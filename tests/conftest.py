"""
Pytest configuration and shared fixtures for unit tests
"""

import asyncio
import os
import pytest
from unittest.mock import MagicMock


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_clob_client():
    """Create a mock CLOB client for testing"""
    mock_client = MagicMock()
    mock_client.wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
    return mock_client


@pytest.fixture
def test_settings():
    """Create a test settings instance with proper environment"""
    # Set required environment variables for testing
    old_env = os.environ.copy()
    os.environ['PRIVATE_KEY'] = '0x1234567890123456789012345678901234567890123456789012345678901234'

    try:
        from config.settings import Settings
        settings = Settings()
        yield settings
    finally:
        # Restore environment
        os.environ.clear()
        os.environ.update(old_env)


# Configure pytest-asyncio
pytest_plugins = ["pytest_asyncio"]
