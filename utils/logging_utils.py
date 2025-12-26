import logging
import sys
import json
import os
from datetime import datetime
from pythonjsonlogger import jsonlogger
from config.settings import settings
import traceback

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging"""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Add timestamp if not present
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        # Add log level
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

        # Add environment info
        log_record['environment'] = os.getenv('ENVIRONMENT', 'production')

        # Add service name
        log_record['service'] = 'polymarket-copy-bot'

        # Add process info
        log_record['process_id'] = os.getpid()
        log_record['thread_id'] = getattr(record, 'thread', None)

        # Mask sensitive data
        if 'data' in log_record and isinstance(log_record['data'], dict):
            log_record['data'] = self._mask_sensitive_data(log_record['data'])

        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = {
                'type': str(record.exc_info[0].__name__),
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_tb(record.exc_info[2])
            }

    def _mask_sensitive_data(self, data):
        """Mask sensitive information in log data"""
        if isinstance(data, dict):
            masked = {}
            for key, value in data.items():
                key_lower = key.lower()
                sensitive_keywords = ['key', 'secret', 'password', 'token', 'auth', 'credential', 'wallet', 'private']

                if any(keyword in key_lower for keyword in sensitive_keywords):
                    masked[key] = '[REDACTED]'
                elif isinstance(value, str):
                    value_clean = value.lower()
                    if value.startswith('0x') and (len(value) == 64 or len(value) == 66 or len(value) == 42):
                        # Private key or wallet address
                        masked[key] = f"{value[:6]}...[REDACTED]"
                    elif any(keyword in value_clean for keyword in ['sk_live', 'pk_live', 'api_key']):
                        masked[key] = '[REDACTED]'
                    else:
                        masked[key] = value
                else:
                    masked[key] = self._mask_sensitive_data(value)
            return masked
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        else:
            return data

def setup_logging():
    """Configure logging for the application"""
    try:
        log_level = getattr(logging, settings.logging.log_level.upper(), logging.INFO)

        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(settings.logging.log_file)
        os.makedirs(log_dir, exist_ok=True)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Clear existing handlers
        root_logger.handlers = []

        # Console handler (human-readable)
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

        # File handler (JSON format)
        file_handler = logging.FileHandler(settings.logging.log_file)
        json_formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s %(data)s %(exception)s'
        )
        file_handler.setFormatter(json_formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

        # Set specific log levels for third-party libraries
        logging.getLogger('web3').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        logging.getLogger('telegram').setLevel(logging.WARNING)
        logging.getLogger('aiohttp').setLevel(logging.WARNING)

        logger = logging.getLogger(__name__)
        logger.info("✅ Logging configured successfully")
        logger.info(f"Log level: {settings.logging.log_level}")
        logger.info(f"Log file: {settings.logging.log_file}")

        return logger

    except Exception as e:
        # Fallback to basic logging if configuration fails
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)
        logger.error(f"Error setting up logging: {e}")
        return logger

def log_performance_metrics(metrics: dict, logger: logging.Logger):
    """Log performance metrics in structured format"""
    logger.info("Performance metrics", extra={'data': metrics})

def log_trade_execution(trade_details: dict, logger: logging.Logger):
    """Log trade execution details"""
    safe_trade = trade_details.copy()
    # Mask sensitive data
    if 'private_key' in safe_trade:
        safe_trade['private_key'] = '[REDACTED]'
    if 'wallet_address' in safe_trade and isinstance(safe_trade['wallet_address'], str):
        safe_trade['wallet_address'] = f"{safe_trade['wallet_address'][:6]}...[REDACTED]"

    logger.info("Trade executed", extra={'data': safe_trade})

def log_error(error: Exception, context: dict = None, logger: logging.Logger = None):
    """Log error with context"""
    if logger is None:
        logger = logging.getLogger(__name__)

    error_context = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'stack_trace': traceback.format_exc()
    }

    if context:
        error_context.update(context)

    logger.error("Error occurred", extra={'data': error_context}, exc_info=True)

if __name__ == "__main__":
    # Test logging setup
    logger = setup_logging()

    logger.info("Test info message")
    logger.warning("Test warning message")
    logger.error("Test error message", extra={'data': {'test_key': 'test_value'}})

    try:
        raise ValueError("Test exception")
    except ValueError as e:
        log_error(e, {'test_context': 'exception_test'}, logger)
