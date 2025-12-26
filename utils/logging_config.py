"""Logging configuration for Polymarket copy bot."""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from logging.handlers import RotatingFileHandler
except ImportError:
    # Fallback for systems without RotatingFileHandler
    RotatingFileHandler = None


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON formatted log entry
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add custom fields from record
        custom_fields = [
            "wallet",
            "wallet_address",
            "trade_id",
            "market_id",
            "condition_id",
            "tx_hash",
            "order_id",
            "amount",
            "price",
            "side",
            "status",
            "balance",
            "gas_price",
            "block_number",
            "latency_ms",
        ]

        for field in custom_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                # Convert non-serializable types
                if isinstance(value, datetime):
                    log_entry[field] = value.isoformat()
                else:
                    log_entry[field] = value

        return json.dumps(log_entry, default=str)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for console output."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s", datefmt="%H:%M:%S"
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human consumption."""
        # Add extra context for certain log levels
        if record.levelno >= logging.ERROR and hasattr(record, "wallet"):
            wallet = getattr(record, "wallet", "unknown")
            record.msg = f"[WALLET:{wallet}] {record.msg}"

        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    console_level: Optional[str] = None,
    json_logging: bool = True,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Root logger level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        console_level: Console logging level (defaults to same as level)
        json_logging: Whether to enable JSON file logging
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True, parents=True)

    # Clear existing handlers
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler - human readable
    console_level = console_level or level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))
    console_handler.setFormatter(HumanFormatter())
    root.addHandler(console_handler)

    # File handler - JSON format for structured logging
    if json_logging and RotatingFileHandler:
        file_handler = RotatingFileHandler(
            log_path / "bot.log",
            maxBytes=10_000_000,  # 10MB per file
            backupCount=5,  # Keep 5 backup files
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_handler.setFormatter(JSONFormatter())
        root.addHandler(file_handler)

    # Reduce noise from third-party libraries
    noisy_libs = [
        "urllib3",
        "urllib3.connectionpool",
        "urllib3.connection",
        "web3",
        "web3.providers",
        "web3.providers.rpc",
        "asyncio",
        "aiohttp",
        "aiohttp.client",
        "aiohttp.server",
        "eth_account",
        "py_clob_client",
        "scipy",
        "numpy",
        "pandas",
        "sklearn",
        "matplotlib",
        "PIL",
    ]

    for lib in noisy_libs:
        logging.getLogger(lib).setLevel(logging.WARNING)

    # Special handling for very noisy libraries
    logging.getLogger("web3.RequestManager").setLevel(logging.ERROR)
    logging.getLogger("web3.providers.rpc.RPCProvider").setLevel(logging.ERROR)

    # Log startup
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "level": level,
            "log_dir": str(log_dir),
            "json_logging": json_logging,
            "console_level": console_level,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Convenience functions for contextual logging
def log_trade_execution(
    logger: logging.Logger,
    trade_id: str,
    wallet: str,
    market_id: str,
    side: str,
    amount: str,
    price: str,
    tx_hash: Optional[str] = None,
) -> None:
    """Log trade execution with full context."""
    logger.info(
        f"Trade executed: {side} {amount} @ ${price}",
        extra={
            "trade_id": trade_id,
            "wallet": wallet,
            "market_id": market_id,
            "side": side,
            "amount": amount,
            "price": price,
            "tx_hash": tx_hash,
        },
    )


def log_wallet_balance(
    logger: logging.Logger, wallet: str, balance: str, currency: str = "USDC"
) -> None:
    """Log wallet balance update."""
    logger.info(
        f"Wallet balance: {balance} {currency}",
        extra={"wallet": wallet, "balance": balance, "currency": currency},
    )


def log_api_call(
    logger: logging.Logger,
    endpoint: str,
    method: str = "GET",
    latency_ms: Optional[int] = None,
    status_code: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """Log API call details."""
    level = logging.ERROR if error or (status_code and status_code >= 400) else logging.DEBUG

    message = f"API call: {method} {endpoint}"
    if latency_ms:
        message += f" ({latency_ms}ms)"
    if status_code:
        message += f" [{status_code}]"
    if error:
        message += f" - {error}"

    logger.log(
        level,
        message,
        extra={
            "endpoint": endpoint,
            "method": method,
            "latency_ms": latency_ms,
            "status_code": status_code,
            "error": error,
        },
    )


def log_transaction_found(
    logger: logging.Logger,
    wallet: str,
    tx_hash: str,
    block_number: Optional[int] = None,
    value: Optional[str] = None,
) -> None:
    """Log when a transaction is found."""
    message = f"Transaction found: {tx_hash[:10]}..."
    if value:
        message += f" (value: {value})"

    logger.info(
        message,
        extra={"wallet": wallet, "tx_hash": tx_hash, "block_number": block_number, "value": value},
    )
