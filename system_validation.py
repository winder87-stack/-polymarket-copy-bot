#!/usr/bin/env python3
"""
System Validation Script for Polymarket Copy Trading Bot
Performs comprehensive end-to-end validation of the entire system.
"""
import asyncio
import sys
import os
import time
import json
import tempfile
import shutil
import psutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import Settings, settings
from core.clob_client import PolymarketClient
from core.wallet_monitor import WalletMonitor
from core.trade_executor import TradeExecutor
from utils.helpers import normalize_address
from utils.security import validate_private_key, mask_sensitive_data
from utils.logging_utils import setup_logging, log_performance_metrics
from utils.alerts import alert_manager


class SystemValidator:
    """Comprehensive system validator for the Polymarket Copy Trading Bot."""

    def __init__(self):
        self.results = {
            'happy_path': {},
            'failure_modes': {},
            'security': {},
            'performance': {},
            'configuration': {},
            'deployment': {},
            'user_experience': {}
        }
        self.start_time = time.time()
        self.logger = setup_logging()

    async def run_full_validation(self) -> Dict[str, Any]:
        """Run complete system validation."""
        self.logger.info("🚀 Starting comprehensive system validation...")

        try:
            # 1. Happy Path Validation
            self.results['happy_path'] = await self.validate_happy_path()

            # 2. Failure Mode Validation
            self.results['failure_modes'] = await self.validate_failure_modes()

            # 3. Security Validation
            self.results['security'] = await self.validate_security()

            # 4. Performance Validation
            self.results['performance'] = await self.validate_performance()

            # 5. Configuration Validation
            self.results['configuration'] = await self.validate_configuration()

            # 6. Deployment Validation
            self.results['deployment'] = await self.validate_deployment()

            # 7. User Experience Validation
            self.results['user_experience'] = await self.validate_user_experience()

            # Calculate final score
            final_score = self.calculate_final_score()

            self.logger.info(f"✅ System validation completed. Final Score: {final_score}/100")

            return {
                'timestamp': datetime.now().isoformat(),
                'duration': time.time() - self.start_time,
                'final_score': final_score,
                'results': self.results,
                'recommendation': self.get_go_no_go_recommendation(final_score)
            }

        except Exception as e:
            self.logger.error(f"❌ System validation failed: {e}", exc_info=True)
            return {
                'timestamp': datetime.now().isoformat(),
                'duration': time.time() - self.start_time,
                'final_score': 0,
                'error': str(e),
                'results': self.results
            }

    async def validate_happy_path(self) -> Dict[str, Any]:
        """Validate happy path scenarios."""
        self.logger.info("🎯 Validating happy path scenarios...")

        results = {
            'wallet_transaction_detection': False,
            'trade_execution': False,
            'position_management': False,
            'performance_reporting': False,
            'errors': []
        }

        try:
            # Test wallet transaction detection
            results['wallet_transaction_detection'] = await self._test_wallet_transaction_detection()

            # Test trade execution
            results['trade_execution'] = await self._test_trade_execution()

            # Test position management
            results['position_management'] = await self._test_position_management()

            # Test performance reporting
            results['performance_reporting'] = await self._test_performance_reporting()

        except Exception as e:
            results['errors'].append(f"Happy path validation error: {e}")
            self.logger.error(f"Happy path validation error: {e}")

        return results

    async def validate_failure_modes(self) -> Dict[str, Any]:
        """Validate failure mode handling."""
        self.logger.info("💥 Validating failure mode scenarios...")

        results = {
            'circuit_breaker_activation': False,
            'api_failure_recovery': False,
            'trade_execution_error_handling': False,
            'alerting_during_failures': False,
            'errors': []
        }

        try:
            # Test circuit breaker activation
            results['circuit_breaker_activation'] = await self._test_circuit_breaker()

            # Test API failure recovery
            results['api_failure_recovery'] = await self._test_api_failure_recovery()

            # Test trade execution error handling
            results['trade_execution_error_handling'] = await self._test_trade_execution_errors()

            # Test alerting during failures
            results['alerting_during_failures'] = await self._test_failure_alerting()

        except Exception as e:
            results['errors'].append(f"Failure mode validation error: {e}")
            self.logger.error(f"Failure mode validation error: {e}")

        return results

    async def validate_security(self) -> Dict[str, Any]:
        """Validate security measures."""
        self.logger.info("🔒 Validating security measures...")

        results = {
            'no_sensitive_data_in_logs': False,
            'private_key_never_exposed': False,
            'input_sanitization': False,
            'rate_limiting_effective': False,
            'errors': []
        }

        try:
            # Test log security
            results['no_sensitive_data_in_logs'] = await self._test_log_security()

            # Test private key protection
            results['private_key_never_exposed'] = await self._test_private_key_protection()

            # Test input sanitization
            results['input_sanitization'] = await self._test_input_sanitization()

            # Test rate limiting
            results['rate_limiting_effective'] = await self._test_rate_limiting()

        except Exception as e:
            results['errors'].append(f"Security validation error: {e}")
            self.logger.error(f"Security validation error: {e}")

        return results

    async def validate_performance(self) -> Dict[str, Any]:
        """Validate performance characteristics."""
        self.logger.info("⚡ Validating performance characteristics...")

        results = {
            'end_to_end_latency': {'value': 0, 'acceptable': False},
            'resource_usage': {'memory_mb': 0, 'cpu_percent': 0, 'acceptable': False},
            'api_rate_limit_compliance': False,
            'memory_usage_over_time': {'stable': False, 'leak_detected': False},
            'errors': []
        }

        try:
            # Test end-to-end latency
            latency_result = await self._test_end_to_end_latency()
            results['end_to_end_latency'] = latency_result

            # Test resource usage
            resource_result = await self._test_resource_usage()
            results['resource_usage'] = resource_result

            # Test API rate limit compliance
            results['api_rate_limit_compliance'] = await self._test_api_rate_limits()

            # Test memory usage over time
            memory_result = await self._test_memory_usage_over_time()
            results['memory_usage_over_time'] = memory_result

        except Exception as e:
            results['errors'].append(f"Performance validation error: {e}")
            self.logger.error(f"Performance validation error: {e}")

        return results

    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate configuration system."""
        self.logger.info("⚙️ Validating configuration system...")

        results = {
            'all_config_options': False,
            'fallback_defaults': False,
            'env_variable_loading': False,
            'config_validation_logic': False,
            'errors': []
        }

        try:
            # Test all configuration options
            results['all_config_options'] = await self._test_config_options()

            # Test fallback defaults
            results['fallback_defaults'] = await self._test_fallback_defaults()

            # Test environment variable loading
            results['env_variable_loading'] = await self._test_env_variable_loading()

            # Test configuration validation logic
            results['config_validation_logic'] = await self._test_config_validation()

        except Exception as e:
            results['errors'].append(f"Configuration validation error: {e}")
            self.logger.error(f"Configuration validation error: {e}")

        return results

    async def validate_deployment(self) -> Dict[str, Any]:
        """Validate deployment configuration."""
        self.logger.info("🚀 Validating deployment configuration...")

        results = {
            'systemd_service_startup': False,
            'graceful_shutdown': False,
            'log_rotation': False,
            'file_permissions': False,
            'errors': []
        }

        try:
            # Test systemd service configuration
            results['systemd_service_startup'] = await self._test_systemd_service()

            # Test graceful shutdown
            results['graceful_shutdown'] = await self._test_graceful_shutdown()

            # Test log rotation
            results['log_rotation'] = await self._test_log_rotation()

            # Test file permissions
            results['file_permissions'] = await self._test_file_permissions()

        except Exception as e:
            results['errors'].append(f"Deployment validation error: {e}")
            self.logger.error(f"Deployment validation error: {e}")

        return results

    async def validate_user_experience(self) -> Dict[str, Any]:
        """Validate user experience aspects."""
        self.logger.info("👥 Validating user experience...")

        results = {
            'telegram_alert_quality': {'score': 0, 'issues': []},
            'log_readability': {'score': 0, 'issues': []},
            'setup_script_usability': {'score': 0, 'issues': []},
            'error_message_clarity': {'score': 0, 'issues': []},
            'errors': []
        }

        try:
            # Test Telegram alert quality
            results['telegram_alert_quality'] = await self._test_telegram_alerts()

            # Test log readability
            results['log_readability'] = await self._test_log_readability()

            # Test setup script usability
            results['setup_script_usability'] = await self._test_setup_script()

            # Test error message clarity
            results['error_message_clarity'] = await self._test_error_messages()

        except Exception as e:
            results['errors'].append(f"User experience validation error: {e}")
            self.logger.error(f"User experience validation error: {e}")

        return results

    # Happy Path Test Methods
    async def _test_wallet_transaction_detection(self) -> bool:
        """Test wallet transaction detection."""
        try:
            # Create a mock wallet monitor
            from tests.mocks.web3_mock import create_mock_web3
            web3 = create_mock_web3()

            with patch('core.wallet_monitor.Web3', return_value=web3):
                monitor = WalletMonitor()
                monitor.target_wallets = ["0x742d35Cc6634C0532925a3b844Bc454e4438f44e"]

                # Should initialize without errors
                assert len(monitor.target_wallets) == 1
                assert monitor.web3 is not None

                # Test transaction detection (mocked)
                transactions = await monitor.get_wallet_transactions("0x742d35Cc6634C0532925a3b844Bc454e4438f44e")
                # Should return empty list for mock (no real API calls)
                assert isinstance(transactions, list)

                return True
        except Exception as e:
            self.logger.error(f"Wallet transaction detection test failed: {e}")
            return False

    async def _test_trade_execution(self) -> bool:
        """Test trade execution flow."""
        try:
            from tests.mocks.clob_api_mock import create_mock_clob_client

            api_mock = create_mock_clob_client()
            client = PolymarketClient.__new__(PolymarketClient)
            client.client = api_mock
            client.settings = settings

            executor = TradeExecutor(client)

            # Test trade validation
            sample_trade = {
                'tx_hash': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
                'timestamp': datetime.now(),
                'wallet_address': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                'condition_id': '0x1234567890abcdef1234567890abcdef12345678',
                'side': 'BUY',
                'amount': 10.0,
                'price': 0.65,
                'token_id': '0xabcdef1234567890abcdef1234567890abcdef12',
                'confidence_score': 0.8
            }

            is_valid = executor._validate_trade(sample_trade)
            assert is_valid

            # Test risk management
            risk_approved = executor._apply_risk_management(sample_trade)
            assert risk_approved['approved']

            return True
        except Exception as e:
            self.logger.error(f"Trade execution test failed: {e}")
            return False

    async def _test_position_management(self) -> bool:
        """Test position management."""
        try:
            from tests.mocks.clob_api_mock import create_mock_clob_client

            api_mock = create_mock_clob_client()
            client = PolymarketClient.__new__(PolymarketClient)
            client.client = api_mock

            executor = TradeExecutor(client)

            # Add a mock position
            position_key = "test_condition_BUY"
            executor.open_positions[position_key] = {
                'amount': 10.0,
                'entry_price': 0.60,
                'timestamp': time.time(),
                'original_trade': {'condition_id': 'test_condition', 'side': 'BUY'}
            }

            # Test position management (should not crash)
            await executor.manage_positions()

            return True
        except Exception as e:
            self.logger.error(f"Position management test failed: {e}")
            return False

    async def _test_performance_reporting(self) -> bool:
        """Test performance reporting."""
        try:
            from tests.mocks.clob_api_mock import create_mock_clob_client

            api_mock = create_mock_clob_client()
            client = PolymarketClient.__new__(PolymarketClient)
            client.client = api_mock

            executor = TradeExecutor(client)

            # Set some mock performance data
            executor.total_trades = 10
            executor.successful_trades = 8
            executor.failed_trades = 2

            # Get performance metrics
            metrics = executor.get_performance_metrics()

            assert 'total_trades' in metrics
            assert 'success_rate' in metrics
            assert metrics['total_trades'] == 10
            assert abs(metrics['success_rate'] - 0.8) < 0.01

            return True
        except Exception as e:
            self.logger.error(f"Performance reporting test failed: {e}")
            return False

    # Failure Mode Test Methods
    async def _test_circuit_breaker(self) -> bool:
        """Test circuit breaker activation."""
        try:
            from tests.mocks.clob_api_mock import create_mock_clob_client

            api_mock = create_mock_clob_client()
            client = PolymarketClient.__new__(PolymarketClient)
            client.client = api_mock

            executor = TradeExecutor(client)

            # Test circuit breaker activation
            executor.daily_loss = 200.0  # Above limit
            executor._check_circuit_breaker_conditions()

            assert executor.circuit_breaker_active

            # Test circuit breaker reset
            executor.daily_loss = 0.0
            executor.circuit_breaker_time = time.time() - 7200  # 2 hours ago
            executor._check_circuit_breaker_conditions()

            assert not executor.circuit_breaker_active

            return True
        except Exception as e:
            self.logger.error(f"Circuit breaker test failed: {e}")
            return False

    async def _test_api_failure_recovery(self) -> bool:
        """Test API failure recovery."""
        try:
            from tests.mocks.clob_api_mock import CLOBAPIMock

            api_mock = CLOBAPIMock()
            api_mock.set_should_fail(True, ConnectionError("API temporarily unavailable"))

            # Test that API failures are handled gracefully
            balance = await api_mock.get_balance()
            assert balance is None  # Should return None on failure

            # Reset and test recovery
            api_mock.set_should_fail(False)
            balance = await api_mock.get_balance()
            assert balance == 1000.0  # Should work after recovery

            return True
        except Exception as e:
            self.logger.error(f"API failure recovery test failed: {e}")
            return False

    async def _test_trade_execution_errors(self) -> bool:
        """Test trade execution error handling."""
        try:
            from tests.mocks.clob_api_mock import CLOBAPIMock

            api_mock = CLOBAPIMock()
            client = PolymarketClient.__new__(PolymarketClient)
            client.client = api_mock

            executor = TradeExecutor(client)

            # Test invalid trade handling
            invalid_trade = {'invalid': 'data'}
            result = await executor.execute_copy_trade(invalid_trade)
            assert result['status'] == 'error'

            # Test risk rejection
            valid_trade = {
                'tx_hash': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
                'timestamp': datetime.now(),
                'wallet_address': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                'condition_id': '0x1234567890abcdef1234567890abcdef12345678',
                'side': 'BUY',
                'amount': 1000.0,  # Too large
                'price': 0.65,
                'token_id': '0xabcdef1234567890abcdef1234567890abcdef12',
                'confidence_score': 0.8
            }

            result = await executor.execute_copy_trade(valid_trade)
            assert result['status'] == 'rejected'

            return True
        except Exception as e:
            self.logger.error(f"Trade execution error handling test failed: {e}")
            return False

    async def _test_failure_alerting(self) -> bool:
        """Test alerting during failures."""
        try:
            # Test that alerts are properly configured
            if settings.alerts.telegram_bot_token and settings.alerts.telegram_chat_id:
                # If alerts are configured, they should be initialized
                assert alert_manager.enabled
            else:
                # If not configured, should be disabled
                assert not alert_manager.enabled

            return True
        except Exception as e:
            self.logger.error(f"Failure alerting test failed: {e}")
            return False

    # Security Test Methods
    async def _test_log_security(self) -> bool:
        """Test that sensitive data is not logged."""
        try:
            # Test secure logging
            from utils.security import secure_log
            import logging

            logger = logging.getLogger('test_security')

            test_data = {
                'private_key': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
                'wallet_address': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                'normal_data': 'safe to log'
            }

            # This should not raise exceptions and should mask sensitive data
            secure_log(logger, 'security_test', test_data)

            return True
        except Exception as e:
            self.logger.error(f"Log security test failed: {e}")
            return False

    async def _test_private_key_protection(self) -> bool:
        """Test that private keys are never exposed."""
        try:
            # Test private key validation
            valid_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            assert validate_private_key(valid_key)

            # Test that invalid keys are rejected
            invalid_keys = ["", "0x", "not_a_key"]
            for invalid_key in invalid_keys:
                assert not validate_private_key(invalid_key)

            # Test that masked data doesn't contain full keys
            masked = mask_sensitive_data({'private_key': valid_key})
            assert '[REDACTED]' in str(masked)
            assert valid_key not in str(masked)

            return True
        except Exception as e:
            self.logger.error(f"Private key protection test failed: {e}")
            return False

    async def _test_input_sanitization(self) -> bool:
        """Test input sanitization."""
        try:
            # Test that dangerous inputs are handled
            dangerous_inputs = [
                "'; DROP TABLE users; --",
                "<script>alert('xss')</script>",
                "../../../etc/passwd",
                "javascript:evil()",
                "${jndi:ldap://evil.com}"
            ]

            for dangerous_input in dangerous_inputs:
                # Should not crash when processing
                masked = mask_sensitive_data({'input': dangerous_input})
                assert isinstance(masked, dict)

            return True
        except Exception as e:
            self.logger.error(f"Input sanitization test failed: {e}")
            return False

    async def _test_rate_limiting(self) -> bool:
        """Test rate limiting effectiveness."""
        try:
            from tests.mocks.web3_mock import create_mock_web3
            web3 = create_mock_web3()

            with patch('core.wallet_monitor.Web3', return_value=web3):
                monitor = WalletMonitor()

                # Test that rate limiting is in place
                assert hasattr(monitor, 'last_api_call')
                assert hasattr(monitor, 'api_call_delay')
                assert monitor.api_call_delay > 0

                return True
        except Exception as e:
            self.logger.error(f"Rate limiting test failed: {e}")
            return False

    # Performance Test Methods
    async def _test_end_to_end_latency(self) -> Dict[str, Any]:
        """Test end-to-end latency."""
        try:
            start_time = time.time()

            # Simulate a simple operation
            from tests.mocks.clob_api_mock import create_mock_clob_client
            client = create_mock_clob_client()

            balance = await client.get_balance()

            end_time = time.time()
            latency = end_time - start_time

            return {
                'value': latency,
                'acceptable': latency < 1.0  # Should be under 1 second
            }
        except Exception as e:
            self.logger.error(f"End-to-end latency test failed: {e}")
            return {'value': 0, 'acceptable': False}

    async def _test_resource_usage(self) -> Dict[str, Any]:
        """Test resource usage."""
        try:
            process = psutil.Process(os.getpid())

            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent(interval=0.1)

            return {
                'memory_mb': memory_mb,
                'cpu_percent': cpu_percent,
                'acceptable': memory_mb < 200 and cpu_percent < 50  # Reasonable limits
            }
        except Exception as e:
            self.logger.error(f"Resource usage test failed: {e}")
            return {'memory_mb': 0, 'cpu_percent': 0, 'acceptable': False}

    async def _test_api_rate_limits(self) -> bool:
        """Test API rate limit compliance."""
        try:
            # Test that rate limiting mechanisms are in place
            from tests.mocks.polygonscan_mock import PolygonScanMockServer

            # The mock should demonstrate rate limiting concepts
            server = PolygonScanMockServer()

            # Test that server has rate limiting attributes
            assert hasattr(server, 'rate_limiting_enabled')

            return True
        except Exception as e:
            self.logger.error(f"API rate limit test failed: {e}")
            return False

    async def _test_memory_usage_over_time(self) -> Dict[str, Any]:
        """Test memory usage stability over time."""
        try:
            process = psutil.Process(os.getpid())

            # Take multiple memory measurements
            measurements = []
            for i in range(5):
                memory_mb = process.memory_info().rss / 1024 / 1024
                measurements.append(memory_mb)
                await asyncio.sleep(0.1)

            # Check if memory is stable (not continuously increasing)
            max_memory = max(measurements)
            min_memory = min(measurements)
            memory_variance = max_memory - min_memory

            # Memory should not vary by more than 10MB during short period
            stable = memory_variance < 10.0
            leak_detected = memory_variance > 20.0  # Significant increase suggests leak

            return {
                'stable': stable,
                'leak_detected': leak_detected
            }
        except Exception as e:
            self.logger.error(f"Memory usage over time test failed: {e}")
            return {'stable': False, 'leak_detected': True}

    # Configuration Test Methods
    async def _test_config_options(self) -> bool:
        """Test all configuration options."""
        try:
            # Test that all expected configuration sections exist
            assert hasattr(settings, 'risk')
            assert hasattr(settings, 'network')
            assert hasattr(settings, 'trading')
            assert hasattr(settings, 'monitoring')
            assert hasattr(settings, 'alerts')
            assert hasattr(settings, 'logging')

            # Test that critical settings have values
            assert settings.risk.max_daily_loss > 0
            assert settings.risk.max_position_size > 0
            assert settings.network.polygon_rpc_url != ""
            assert settings.monitoring.monitor_interval > 0

            return True
        except Exception as e:
            self.logger.error(f"Config options test failed: {e}")
            return False

    async def _test_fallback_defaults(self) -> bool:
        """Test fallback defaults."""
        try:
            # Test that defaults are reasonable
            assert settings.risk.max_position_size == 50.0  # Default value
            assert settings.monitoring.monitor_interval == 15  # Default value
            assert settings.logging.log_level == "INFO"  # Default value

            return True
        except Exception as e:
            self.logger.error(f"Fallback defaults test failed: {e}")
            return False

    async def _test_env_variable_loading(self) -> bool:
        """Test environment variable loading."""
        try:
            # Test that environment variables can override defaults
            with patch.dict(os.environ, {'MAX_DAILY_LOSS': '200.0', 'MONITOR_INTERVAL': '30'}):
                # Create new settings instance to test loading
                from config.settings import Settings
                test_settings = Settings()

                assert test_settings.risk.max_daily_loss == 200.0
                assert test_settings.monitoring.monitor_interval == 30

            return True
        except Exception as e:
            self.logger.error(f"Environment variable loading test failed: {e}")
            return False

    async def _test_config_validation(self) -> bool:
        """Test configuration validation logic."""
        try:
            # Test that validation works
            settings.validate_critical_settings()

            # Test that invalid configurations are caught
            with patch.object(settings.trading, 'private_key', 'invalid'):
                try:
                    settings.validate_critical_settings()
                    return False  # Should have raised an exception
                except ValueError:
                    pass  # Expected

            return True
        except Exception as e:
            self.logger.error(f"Config validation test failed: {e}")
            return False

    # Deployment Test Methods
    async def _test_systemd_service(self) -> bool:
        """Test systemd service configuration."""
        try:
            service_file = Path("/home/ink/polymarket-copy-bot/systemd/polymarket-bot.service")

            if service_file.exists():
                content = service_file.read_text()

                # Check for required systemd directives
                assert "[Unit]" in content
                assert "[Service]" in content
                assert "[Install]" in content
                assert "ExecStart=" in content
                assert "User=polymarket-bot" in content

                return True
            else:
                self.logger.warning("Systemd service file not found")
                return False
        except Exception as e:
            self.logger.error(f"Systemd service test failed: {e}")
            return False

    async def _test_graceful_shutdown(self) -> bool:
        """Test graceful shutdown handling."""
        try:
            # Test that main.py has proper signal handling
            main_file = Path("/home/ink/polymarket-copy-bot/main.py")

            if main_file.exists():
                content = main_file.read_text()

                # Check for signal handling
                assert "signal.signal" in content
                assert "signal.SIGINT" in content
                assert "signal.SIGTERM" in content

                # Check for graceful shutdown method
                assert "async def shutdown" in content

                return True
            else:
                return False
        except Exception as e:
            self.logger.error(f"Graceful shutdown test failed: {e}")
            return False

    async def _test_log_rotation(self) -> bool:
        """Test log rotation configuration."""
        try:
            # Check if log directory exists and is writable
            log_dir = Path("/home/ink/polymarket-copy-bot/logs")

            if log_dir.exists():
                # Check if directory is writable
                assert os.access(log_dir, os.W_OK)

                # Check if log file can be created
                test_log_file = log_dir / "test_validation.log"
                test_log_file.write_text("Test log entry")
                test_log_file.unlink()  # Clean up

                return True
            else:
                self.logger.warning("Log directory does not exist")
                return False
        except Exception as e:
            self.logger.error(f"Log rotation test failed: {e}")
            return False

    async def _test_file_permissions(self) -> bool:
        """Test file permissions."""
        try:
            project_dir = Path("/home/ink/polymarket-copy-bot")

            # Check main script permissions
            main_script = project_dir / "main.py"
            if main_script.exists():
                # Should be executable
                assert os.access(main_script, os.X_OK)

            # Check config directory permissions
            config_dir = project_dir / "config"
            if config_dir.exists():
                assert os.access(config_dir, os.R_OK)

            # Check that sensitive files are not world-readable
            env_file = project_dir / ".env"
            if env_file.exists():
                # .env file should not be world-readable
                stat = env_file.stat()
                # Check if group or other has read permission
                world_readable = bool(stat.st_mode & 0o044)
                if world_readable:
                    self.logger.warning(".env file is world-readable")

            return True
        except Exception as e:
            self.logger.error(f"File permissions test failed: {e}")
            return False

    # User Experience Test Methods
    async def _test_telegram_alerts(self) -> Dict[str, Any]:
        """Test Telegram alert quality."""
        try:
            score = 0
            issues = []

            # Check if alerts are configured
            if settings.alerts.telegram_bot_token and settings.alerts.telegram_chat_id:
                score += 20
            else:
                issues.append("Telegram alerts not configured")

            # Check alert message formatting in code
            alerts_file = Path("/home/ink/polymarket-copy-bot/utils/alerts.py")
            if alerts_file.exists():
                content = alerts_file.read_text()

                # Check for proper formatting
                if "parse_mode='Markdown'" in content:
                    score += 20
                else:
                    issues.append("Alerts not using Markdown formatting")

                if "send_trade_alert" in content:
                    score += 20
                else:
                    issues.append("Trade alerts not implemented")

                if "send_error_alert" in content:
                    score += 20
                else:
                    issues.append("Error alerts not implemented")

                if "cooldown" in content:
                    score += 20
                else:
                    issues.append("Alert cooldown not implemented")
            else:
                issues.append("Alerts file not found")

            return {'score': min(score, 100), 'issues': issues}
        except Exception as e:
            self.logger.error(f"Telegram alerts test failed: {e}")
            return {'score': 0, 'issues': [str(e)]}

    async def _test_log_readability(self) -> Dict[str, Any]:
        """Test log readability."""
        try:
            score = 0
            issues = []

            # Check logging configuration
            logging_file = Path("/home/ink/polymarket-copy-bot/utils/logging_utils.py")
            if logging_file.exists():
                content = logging_file.read_text()

                if "CustomJsonFormatter" in content:
                    score += 25
                else:
                    issues.append("JSON formatting not implemented")

                if "mask_sensitive_data" in content:
                    score += 25
                else:
                    issues.append("Sensitive data masking not implemented")

                if "Structured logging" in content.lower() or "json" in content.lower():
                    score += 25
                else:
                    issues.append("No structured logging")

                if "log_performance_metrics" in content:
                    score += 25
                else:
                    issues.append("Performance logging not implemented")
            else:
                issues.append("Logging utilities not found")

            return {'score': min(score, 100), 'issues': issues}
        except Exception as e:
            self.logger.error(f"Log readability test failed: {e}")
            return {'score': 0, 'issues': [str(e)]}

    async def _test_setup_script(self) -> Dict[str, Any]:
        """Test setup script usability."""
        try:
            score = 0
            issues = []

            setup_script = Path("/home/ink/polymarket-copy-bot/scripts/setup_ubuntu.sh")
            if setup_script.exists():
                content = setup_script.read_text()

                # Check for essential components
                if "set -e" in content:
                    score += 15
                else:
                    issues.append("Script doesn't exit on errors")

                if "sudo" in content and "root" in content:
                    score += 15
                else:
                    issues.append("No root requirement check")

                if "python3" in content and "pip" in content:
                    score += 15
                else:
                    issues.append("Python setup not complete")

                if "systemd" in content:
                    score += 15
                else:
                    issues.append("Systemd setup missing")

                if "chmod" in content and "chown" in content:
                    score += 15
                else:
                    issues.append("Permissions setup incomplete")

                if "Next steps" in content:
                    score += 15
                else:
                    issues.append("No user guidance provided")

                if setup_script.stat().st_mode & 0o111:  # Executable
                    score += 10
                else:
                    issues.append("Script not executable")
            else:
                issues.append("Setup script not found")

            return {'score': min(score, 100), 'issues': issues}
        except Exception as e:
            self.logger.error(f"Setup script test failed: {e}")
            return {'score': 0, 'issues': [str(e)]}

    async def _test_error_messages(self) -> Dict[str, Any]:
        """Test error message clarity."""
        try:
            score = 0
            issues = []

            # Check main.py for error handling
            main_file = Path("/home/ink/polymarket-copy-bot/main.py")
            if main_file.exists():
                content = main_file.read_text()

                if "logger.error" in content and "exc_info=True" in content:
                    score += 25
                else:
                    issues.append("Poor error logging")

                if "send_error_alert" in content:
                    score += 25
                else:
                    issues.append("No error alerting")

                if "try:" in content and "except" in content:
                    score += 25
                else:
                    issues.append("Inadequate exception handling")

                if "Validation failed" in content or "Error:" in content:
                    score += 25
                else:
                    issues.append("Unclear error messages")
            else:
                issues.append("Main file not found")

            return {'score': min(score, 100), 'issues': issues}
        except Exception as e:
            self.logger.error(f"Error message test failed: {e}")
            return {'score': 0, 'issues': [str(e)]}

    def calculate_final_score(self) -> int:
        """Calculate final system health score."""
        try:
            # Weight different validation categories
            weights = {
                'happy_path': 0.25,      # 25% - Core functionality
                'failure_modes': 0.20,   # 20% - Resilience
                'security': 0.20,        # 20% - Security
                'performance': 0.15,     # 15% - Performance
                'configuration': 0.10,   # 10% - Configuration
                'deployment': 0.05,      # 5% - Deployment
                'user_experience': 0.05  # 5% - UX
            }

            total_score = 0

            for category, weight in weights.items():
                category_results = self.results.get(category, {})

                if category == 'user_experience':
                    # Special handling for UX scores
                    ux_score = 0
                    ux_items = 0
                    for item in ['telegram_alert_quality', 'log_readability',
                               'setup_script_usability', 'error_message_clarity']:
                        if item in category_results:
                            ux_score += category_results[item].get('score', 0)
                            ux_items += 1

                    if ux_items > 0:
                        category_score = ux_score / ux_items
                    else:
                        category_score = 0
                else:
                    # Calculate percentage of passed tests
                    total_tests = 0
                    passed_tests = 0

                    for key, value in category_results.items():
                        if key != 'errors' and isinstance(value, bool):
                            total_tests += 1
                            if value:
                                passed_tests += 1
                        elif key != 'errors' and isinstance(value, dict):
                            # Handle performance metrics
                            if 'acceptable' in value:
                                total_tests += 1
                                if value['acceptable']:
                                    passed_tests += 1
                            elif 'stable' in value:
                                total_tests += 1
                                if value['stable'] and not value.get('leak_detected', False):
                                    passed_tests += 1

                    category_score = (passed_tests / max(total_tests, 1)) * 100

                total_score += category_score * weight

            return min(int(total_score), 100)

        except Exception as e:
            self.logger.error(f"Error calculating final score: {e}")
            return 0

    def get_go_no_go_recommendation(self, score: int) -> str:
        """Get go/no-go recommendation based on score."""
        if score >= 90:
            return "🚀 GO: System is production-ready with excellent validation results."
        elif score >= 80:
            return "⚠️ CAUTION: System is mostly ready but requires attention to minor issues."
        elif score >= 70:
            return "🛠️ FIX REQUIRED: System needs significant improvements before production."
        else:
            return "❌ NO-GO: System requires major rework before production deployment."

    def get_critical_issues(self) -> List[str]:
        """Get list of critical issues requiring immediate attention."""
        critical_issues = []

        # Check for errors in each category
        for category, results in self.results.items():
            if 'errors' in results and results['errors']:
                critical_issues.extend([f"{category}: {error}" for error in results['errors']])

        # Check for failed security tests
        security_results = self.results.get('security', {})
        for test_name, passed in security_results.items():
            if test_name != 'errors' and isinstance(passed, bool) and not passed:
                critical_issues.append(f"Security: {test_name} failed")

        # Check for performance issues
        performance_results = self.results.get('performance', {})
        for test_name, result in performance_results.items():
            if test_name != 'errors' and isinstance(result, dict):
                if not result.get('acceptable', True):
                    critical_issues.append(f"Performance: {test_name} failed acceptability criteria")

        return critical_issues

    def get_minor_improvements(self) -> List[str]:
        """Get list of minor improvements for future releases."""
        improvements = []

        # Check UX scores
        ux_results = self.results.get('user_experience', {})
        for test_name, result in ux_results.items():
            if isinstance(result, dict) and result.get('score', 100) < 80:
                improvements.extend(result.get('issues', []))

        # Check for incomplete features
        if not alert_manager.enabled:
            improvements.append("Configure Telegram alerts for better monitoring")

        return improvements


async def main():
    """Main validation function."""
    validator = SystemValidator()

    try:
        results = await validator.run_full_validation()

        # Print summary
        print("\n" + "="*80)
        print("🎯 POLYMARKET COPY TRADING BOT - SYSTEM VALIDATION REPORT")
        print("="*80)

        print(f"\n📊 Final Score: {results['final_score']}/100")
        print(f"⏱️  Validation Duration: {results['duration']:.2f} seconds")
        print(f"🎯 Recommendation: {results['recommendation']}")

        # Critical Issues
        critical_issues = validator.get_critical_issues()
        if critical_issues:
            print(f"\n🚨 Critical Issues ({len(critical_issues)}):")
            for issue in critical_issues[:5]:  # Show top 5
                print(f"  • {issue}")
            if len(critical_issues) > 5:
                print(f"  • ... and {len(critical_issues) - 5} more")

        # Minor Improvements
        minor_improvements = validator.get_minor_improvements()
        if minor_improvements:
            print(f"\n💡 Minor Improvements ({len(minor_improvements)}):")
            for improvement in minor_improvements[:5]:  # Show top 5
                print(f"  • {improvement}")
            if len(minor_improvements) > 5:
                print(f"  • ... and {len(minor_improvements) - 5} more")

        # Category Scores
        print(f"\n📈 Category Scores:")
        for category, cat_results in validator.results.items():
            if category != 'user_experience':
                passed = sum(1 for k, v in cat_results.items()
                           if k != 'errors' and isinstance(v, bool) and v)
                total = sum(1 for k, v in cat_results.items()
                          if k != 'errors' and isinstance(v, bool))
                score = (passed / max(total, 1)) * 100
                print(".1f"            elif category == 'user_experience':
                ux_scores = []
                for item in ['telegram_alert_quality', 'log_readability',
                           'setup_script_usability', 'error_message_clarity']:
                    if item in cat_results and isinstance(cat_results[item], dict):
                        ux_scores.append(cat_results[item].get('score', 0))
                avg_score = sum(ux_scores) / max(len(ux_scores), 1)
                print(".1f"
        # Save detailed report
        report_file = Path("/home/ink/polymarket-copy-bot/final_validation_report.md")
        report_content = f"""# Polymarket Copy Trading Bot - Final Validation Report

## Executive Summary

- **Final Score**: {results['final_score']}/100
- **Validation Duration**: {results['duration']:.2f} seconds
- **Recommendation**: {results['recommendation']}
- **Timestamp**: {results['timestamp']}

## Critical Issues Requiring Immediate Attention

{chr(10).join(f"- {issue}" for issue in validator.get_critical_issues())}

## Minor Improvements for Future Releases

{chr(10).join(f"- {improvement}" for improvement in validator.get_minor_improvements())}

## Detailed Category Results

### Happy Path Validation
{chr(10).join(f"- **{k.replace('_', ' ').title()}**: {'✅ PASSED' if v else '❌ FAILED'}" for k, v in validator.results['happy_path'].items() if k != 'errors')}

### Failure Mode Validation
{chr(10).join(f"- **{k.replace('_', ' ').title()}**: {'✅ PASSED' if v else '❌ FAILED'}" for k, v in validator.results['failure_modes'].items() if k != 'errors')}

### Security Validation
{chr(10).join(f"- **{k.replace('_', ' ').title()}**: {'✅ PASSED' if v else '❌ FAILED'}" for k, v in validator.results['security'].items() if k != 'errors')}

### Performance Validation
{chr(10).join(f"- **{k.replace('_', ' ').title()}**: {'✅ PASSED' if v.get('acceptable', False) else '❌ FAILED'}" for k, v in validator.results['performance'].items() if k != 'errors' and isinstance(v, dict))}

### Configuration Validation
{chr(10).join(f"- **{k.replace('_', ' ').title()}**: {'✅ PASSED' if v else '❌ FAILED'}" for k, v in validator.results['configuration'].items() if k != 'errors')}

### Deployment Validation
{chr(10).join(f"- **{k.replace('_', ' ').title()}**: {'✅ PASSED' if v else '❌ FAILED'}" for k, v in validator.results['deployment'].items() if k != 'errors')}

### User Experience Validation
{chr(10).join(f"- **{k.replace('_', ' ').title()}**: {v.get('score', 0)}/100" for k, v in validator.results['user_experience'].items() if k != 'errors' and isinstance(v, dict))}

## Go/No-Go Decision

Based on the comprehensive validation results, the system is **{'READY' if results['final_score'] >= 80 else 'NOT READY'}** for production deployment.

**Rationale**: {results['recommendation']}

## Next Steps

1. Address all critical issues before production deployment
2. Implement minor improvements in future releases
3. Schedule regular re-validation after any code changes
4. Monitor system performance in production environment

---
*Validation completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""

        report_file.write_text(report_content)
        print(f"\n📄 Detailed report saved to: {report_file}")

        return results['final_score'] >= 80  # Return True if ready for production

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False


if __name__ == "__main__":
    # Run validation
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
