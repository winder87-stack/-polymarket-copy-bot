import hashlib
import json
import logging
import os
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


def secure_log(
    logger: logging.Logger, action: str, data: Dict[str, Any], level: str = "info"
) -> None:
    """Log sensitive data securely by masking sensitive information"""
    try:
        # Create a copy of the data to avoid modifying the original
        safe_data = {}
        for key, value in data.items():
            safe_data[key] = _mask_sensitive_value(key, value)

        # Create log message
        log_message = f"{action}: {json.dumps(safe_data, indent=2)}"

        # Log at appropriate level
        if level.lower() == "error":
            logger.error(log_message)
        elif level.lower() == "warning":
            logger.warning(log_message)
        elif level.lower() == "debug":
            logger.debug(log_message)
        else:
            logger.info(log_message)

    except Exception as e:
        # Fallback to basic logging if secure logging fails
        logger.error(f"Secure logging failed: {e}")
        logger.info(f"{action}: {str(data)}")


def _mask_sensitive_value(key: str, value: Any) -> Any:
    """Mask sensitive values based on key or value patterns"""
    if value is None:
        return None

    key_lower = str(key).lower()
    sensitive_keywords = [
        "key",
        "secret",
        "password",
        "token",
        "auth",
        "credential",
        "wallet",
        "private",
        "signature",
    ]

    # Check if key contains sensitive keywords
    if any(keyword in key_lower for keyword in sensitive_keywords):
        return _mask_value(value)

    # Check value type and content
    if isinstance(value, str):
        value_lower = value.lower()

        # Private key detection
        if value.startswith("0x") and (len(value) == 64 or len(value) == 66):
            return f"{value[:6]}...[REDACTED]"

        # Wallet address detection (partially mask)
        if re.match(r"^0x[a-fA-F0-9]{40}$", value):
            return f"{value[:6]}...{value[-4:]}"

        # API key detection
        if any(
            keyword in value_lower for keyword in ["sk_live", "pk_live", "api_key", "secret_key"]
        ):
            return "[REDACTED]"

    elif isinstance(value, dict):
        # Recursively mask dictionary values
        return {k: _mask_sensitive_value(k, v) for k, v in value.items()}

    elif isinstance(value, list):
        # Recursively mask list items
        return [_mask_sensitive_value(f"item_{i}", item) for i, item in enumerate(value)]

    return value


def _mask_value(value: Any) -> str:
    """Mask a value completely"""
    if isinstance(value, str) and len(value) > 4:
        return f"{str(value)[:4]}...[REDACTED]"
    return "[REDACTED]"


def validate_private_key(key: str) -> bool:
    """Validate private key format"""
    if not key:
        return False

    # Remove 0x prefix if present
    key_clean = key[2:] if key.startswith("0x") else key

    # Check length (64 hex characters)
    if len(key_clean) != 64:
        return False

    # Check if it's valid hex
    try:
        int(key_clean, 16)
        return True
    except ValueError:
        return False


def mask_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive data in any structure"""
    return _mask_sensitive_value("root", data)


def get_environment_hash() -> str:
    """Generate a hash of the environment for debugging (without sensitive data)"""
    env_vars = {}
    for key in os.environ.keys():
        # Skip sensitive environment variables
        key_lower = key.lower()
        if any(
            sensitive in key_lower
            for sensitive in ["key", "secret", "password", "token", "auth", "wallet", "private"]
        ):
            continue
        env_vars[key] = os.environ[key]

    env_str = json.dumps(env_vars, sort_keys=True)
    return hashlib.md5(env_str.encode()).hexdigest()[:8]


def generate_session_id() -> str:
    """Generate a unique session ID for tracking"""
    import uuid

    return str(uuid.uuid4())[:8]


def secure_compare(a: str, b: str) -> bool:
    """Secure string comparison to prevent timing attacks"""
    if len(a) != len(b):
        return False

    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


if __name__ == "__main__":
    # Test the secure logging
    test_data = {
        "private_key": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "wallet_address": "0xabcdef1234567890abcdef1234567890abcdef12",
        "api_key": "sk_live_1234567890abcdef1234567890abcdef",
        "amount": 100.0,
        "token_id": "0x1234567890abcdef1234567890abcdef12345678",
        "password": "mysecretpassword",
        "nested": {"secret_key": "nested_secret_value", "data": [1, 2, 3, "sensitive_data"]},
    }

    logging.basicConfig(level=logging.INFO)
    secure_log(logger, "test_action", test_data)
