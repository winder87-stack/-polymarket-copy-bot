import json
import logging
import os
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler

from pythonjsonlogger import jsonlogger

from config.settings import settings
from utils.logging_security import SecureLogger, SensitiveDataMasker, get_log_security_manager


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging with comprehensive security"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._masker = SensitiveDataMasker()

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Add timestamp if not present
        if not log_record.get("timestamp"):
            log_record["timestamp"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Add log level
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname

        # Add environment info
        log_record["environment"] = os.getenv("ENVIRONMENT", "production")

        # Add service name
        log_record["service"] = "polymarket-copy-bot"

        # Add process info
        log_record["process_id"] = os.getpid()
        log_record["thread_id"] = getattr(record, "thread", None)

        # Mask sensitive data using comprehensive masking
        if "data" in log_record:
            log_record["data"] = self._masker.mask_sensitive_data(
                log_record["data"], context="log_record"
            )

        # Also check for any sensitive data in the message itself
        if "message" in log_record and isinstance(log_record["message"], str):
            log_record["message"] = self._masker.mask_sensitive_data(
                log_record["message"], context="log_message"
            )

        # Add exception info if present (but mask sensitive data in traceback)
        if record.exc_info:
            exception_info = {
                "type": str(record.exc_info[0].__name__),
                "message": self._masker.mask_sensitive_data(
                    str(record.exc_info[1]), context="exception_message"
                ),
                "traceback": self._masker.mask_sensitive_data(
                    "".join(traceback.format_tb(record.exc_info[2])), context="exception_traceback"
                ),
            }
            log_record["exception"] = exception_info


def setup_logging() -> None:
    """Configure secure logging for the application with comprehensive data protection"""
    try:
        log_level = getattr(logging, settings.logging.log_level.upper(), logging.INFO)

        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(settings.logging.log_file)
        os.makedirs(log_dir, exist_ok=True)

        # Get log security manager
        log_security = get_log_security_manager(settings.logging.log_file)

        # Secure log file permissions
        log_security.secure_file_permissions()

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Clear existing handlers
        root_logger.handlers = []

        # Console handler (human-readable)
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

        # Secure rotating file handler (JSON format) with custom rotation
        class SecureRotatingFileHandler(RotatingFileHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.log_security = get_log_security_manager(self.baseFilename)

            def doRollover(self):
                """Override rollover to use secure rotation"""
                super().doRollover()
                # Apply secure permissions to rotated files
                self.log_security.secure_file_permissions()
                # Audit the rotation
                SecureLogger.audit_log(
                    "log_rotation_performed",
                    {"file_path": self.baseFilename, "action": "automatic_rotation"},
                )

        file_handler = SecureRotatingFileHandler(
            settings.logging.log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB per file
            backupCount=5,
            encoding="utf-8",
        )
        json_formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s %(data)s %(exception)s"
        )
        file_handler.setFormatter(json_formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

        # Monitor log file security
        log_security.monitor_log_access()

        # Set specific log levels for third-party libraries
        logging.getLogger("web3").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.WARNING)
        logging.getLogger("aiohttp").setLevel(logging.WARNING)

        logger = logging.getLogger(__name__)
        # Use secure logging for the setup confirmation
        SecureLogger.log(
            "info",
            "✅ Secure logging configured successfully",
            {
                "log_level": settings.logging.log_level,
                "log_file": settings.logging.log_file,
                "security_enabled": True,
            },
        )

        return logger

    except Exception as e:
        # Fallback to basic logging if configuration fails
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        logger = logging.getLogger(__name__)
        logger.error(f"Error setting up secure logging: {e}")
        return logger


def log_performance_metrics(metrics: dict, logger: logging.Logger) -> None:
    """Log performance metrics in structured format with secure masking"""
    SecureLogger.log("info", "Performance metrics", data=metrics, context={"logger": logger.name})


def log_trade_execution(trade_details: dict, logger: logging.Logger) -> None:
    """Log trade execution details with comprehensive security"""
    # The SensitiveDataMasker will handle all masking automatically
    SecureLogger.log(
        "info",
        "Trade executed",
        data=trade_details,
        context={"logger": logger.name, "action": "trade_execution"},
    )


def log_error(error: Exception, context: dict = None, logger: logging.Logger = None) -> None:
    """Log error with context using secure logging"""
    error_context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "stack_trace": traceback.format_exc(),
    }

    if context:
        error_context.update(context)

    # Use secure logging which will mask sensitive data in context
    SecureLogger.log("error", "Error occurred", data=error_context, exc_info=True)


if __name__ == "__main__":
    # Test secure logging setup
    logger = setup_logging()

    # Test secure logging with sensitive data
    SecureLogger.log("info", "Test info message")
    SecureLogger.log("warning", "Test warning message")
    SecureLogger.log(
        "error",
        "Test error message",
        {
            "test_key": "test_value",
            "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
        },
    )

    try:
        raise ValueError("Test exception")
    except ValueError as e:
        log_error(e, {"test_context": "exception_test"}, logger)
