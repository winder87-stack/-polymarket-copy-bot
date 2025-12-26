"""Utility functions for the Polymarket copy bot."""

import asyncio  # For asynchronous operations and sleep functionality
import json  # For JSON parsing and serialization
import logging
import re
from collections import OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal
from time import time
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


def normalize_address(address: str) -> str:
    """
    Normalize Ethereum address format.

    Args:
        address: Ethereum address to normalize

    Returns:
        Normalized address in lowercase with 0x prefix, or empty string if invalid
    """
    if not address:
        return ""

    # Remove 0x prefix if present and ensure lowercase
    address_clean: str = address.lower().replace("0x", "")

    # Validate address length (should be 40 hex characters)
    if len(address_clean) != 40:
        logger.warning(f"Invalid address length: {address_clean} (length: {len(address_clean)})")
        return f"0x{address_clean}"  # Return as-is but with 0x prefix

    return f"0x{address_clean}"


def wei_to_usdc(wei_amount: Union[int, float, str]) -> Decimal:
    """
    Convert wei to USDC (6 decimals).

    Args:
        wei_amount: Amount in wei to convert

    Returns:
        Amount in USDC as Decimal
    """
    try:
        wei = int(wei_amount)
        return Decimal(wei) / Decimal(10**6)
    except (ValueError, TypeError) as e:
        logger.error(f"Error converting wei to USDC: {e}")
        return Decimal("0.0")


def usdc_to_wei(usdc_amount: Union[int, float, str, Decimal]) -> int:
    """
    Convert USDC to wei (6 decimals).

    Args:
        usdc_amount: Amount in USDC to convert

    Returns:
        Amount in wei as integer
    """
    try:
        amount = Decimal(usdc_amount)
        return int(amount * Decimal(10**6))
    except (ValueError, TypeError, ArithmeticError) as e:
        logger.error(f"Error converting USDC to wei: {e}")
        return 0


def calculate_confidence_score(tx: dict[str, Any], patterns: Optional[list[str]] = None) -> float:
    """
    Calculate confidence score for a detected trade.

    Args:
        tx: Transaction data dictionary
        patterns: Optional list of regex patterns to match against transaction input

    Returns:
        Confidence score between 0.0 and 1.0
    """
    score = 0.3  # Base score

    # Value-based scoring
    value = int(tx.get("value", 0))
    if value > 0:
        score += 0.2
    else:
        # Check if it's a contract interaction with data
        input_data = tx.get("input", "")
        if input_data and input_data != "0x":
            score += 0.3

    # Gas usage scoring
    gas_used = int(tx.get("gasUsed", 0))
    if 50000 < gas_used < 500000:  # Typical range for Polymarket trades
        score += 0.2
    elif gas_used > 10000:
        score += 0.1

    # Input data length scoring
    input_data = tx.get("input", "")
    if len(input_data) > 100:  # Likely has function parameters
        score += 0.1

    # Pattern matching scoring
    if patterns:
        input_data_lower = input_data.lower()
        for pattern in patterns:
            if re.search(pattern, input_data_lower):
                score += 0.1
                break

    return min(score, 1.0)


def calculate_position_size(
    original_amount: float,
    account_balance: float,
    max_position_size: float,
    risk_percentage: float = 0.01,
) -> float:
    """Calculate position size based on risk management rules"""
    try:
        # Calculate risk-based size (1% of account per trade)
        risk_based_size = account_balance * risk_percentage

        # Calculate proportional size (10% of original trade)
        proportional_size = original_amount * 0.1

        # Take the minimum of both approaches, capped by max position size
        position_size = min(risk_based_size, proportional_size, max_position_size)

        # Ensure minimum trade amount
        min_trade_amount = 1.0  # USDC
        position_size = max(position_size, min_trade_amount)

        return position_size

    except Exception as e:
        logger.error(f"Error calculating position size: {e}")
        return min(original_amount * 0.1, max_position_size)


def format_currency(amount: float) -> str:
    """Format currency amount with proper decimals"""
    if amount >= 1000:
        return f"${amount:,.2f}"
    elif amount >= 1:
        return f"${amount:.2f}"
    else:
        return f"${amount:.4f}"


def get_time_ago(timestamp: datetime) -> str:
    """Get human-readable time ago string"""
    now = datetime.now()
    diff = now - timestamp

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        seconds = diff.seconds
        return f"{seconds} second{'s' if seconds != 1 else ''} ago"


def truncate_string(text: str, max_length: int = 50) -> str:
    """Truncate string with ellipsis"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def safe_json_parse(json_str: str) -> Optional[Dict[str, Any]]:
    """Safely parse JSON string"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Error parsing JSON: {e}")
        return None


def get_environment_info() -> Dict[str, Any]:
    """Get environment information for debugging"""
    import platform
    import sys

    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "timestamp": datetime.now().isoformat(),
        "environment_hash": generate_environment_hash(),
    }


def generate_environment_hash() -> str:
    """Generate a hash of non-sensitive environment variables"""
    import hashlib
    import os

    env_vars = {}
    for key in sorted(os.environ.keys()):
        key_lower = key.lower()
        # Skip sensitive environment variables
        if any(
            sensitive in key_lower
            for sensitive in ["key", "secret", "password", "token", "auth", "wallet", "private"]
        ):
            continue
        env_vars[key] = os.environ[key]

    env_str = json.dumps(env_vars, sort_keys=True)
    return hashlib.md5(env_str.encode()).hexdigest()[:8]


def retry_with_backoff(max_attempts: int = 3, base_delay: float = 1.0):
    """Decorator for retrying functions with exponential backoff"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f} seconds..."
                    )
                    await asyncio.sleep(delay)
            return None

        return wrapper

    return decorator


class BoundedCache:
    """Efficient TTL-based cache with size limits using OrderedDict for LRU eviction."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        """
        Initialize the bounded cache.

        Args:
            max_size: Maximum number of items to store
            ttl_seconds: Time-to-live in seconds for cache entries
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._timestamps: dict[str, float] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache with TTL check.

        Args:
            key: Cache key to look up

        Returns:
            Cached value if found and not expired, None otherwise
        """
        now: float = time()
        self._cleanup_expired()

        if key in self._cache:
            # Move to end (most recently used)
            value = self._cache.pop(key)
            timestamp = self._timestamps.pop(key)
            self._cache[key] = value
            self._timestamps[key] = timestamp

            if now - timestamp < self.ttl_seconds:
                self._hits += 1
                return value
            else:
                # Entry expired during access
                del self._cache[key]
                del self._timestamps[key]

        self._misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache with cleanup and size enforcement.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cleanup_expired()
        self._enforce_size_limit()

        now: float = time()
        if key in self._cache:
            # Update existing entry, move to end
            self._cache.pop(key)
            self._timestamps.pop(key)

        self._cache[key] = value
        self._timestamps[key] = now

    def _cleanup_expired(self) -> None:
        """Remove expired entries"""
        now = time()
        expired_keys = [
            key for key, timestamp in self._timestamps.items() if now - timestamp > self.ttl_seconds
        ]

        for key in expired_keys:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)
            self._evictions += 1

    def _enforce_size_limit(self) -> None:
        """Enforce maximum cache size using LRU eviction"""
        while len(self._cache) >= self.max_size:
            # Remove oldest (least recently used) entry
            oldest_key, _ = self._cache.popitem(last=False)
            self._timestamps.pop(oldest_key, None)
            self._evictions += 1

    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._timestamps.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache performance metrics
        """
        total_requests: int = self._hits + self._misses
        hit_ratio: float = (self._hits / total_requests) if total_requests > 0 else 0.0

        oldest_timestamp: float = min(self._timestamps.values()) if self._timestamps else time()
        age_seconds: float = time() - oldest_timestamp

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hit_ratio": hit_ratio,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "oldest_entry_age_seconds": age_seconds,
            "ttl_seconds": self.ttl_seconds,
        }


if __name__ == "__main__":
    # Test helpers
    print(f"Normalized address: {normalize_address('0xAbcdef1234567890abcdef1234567890AbcdEf12')}")
    print(f"100 USDC in wei: {usdc_to_wei(100)}")
    print(f"1000000 wei in USDC: {wei_to_usdc(1000000)}")
    print(f"Formatted currency: {format_currency(1234.5678)}")
    print(f"Time ago: {get_time_ago(datetime.now() - timedelta(hours=2))}")
