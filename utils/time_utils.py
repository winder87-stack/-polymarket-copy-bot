"""Time utilities with proper timezone handling.

This module provides timezone-aware datetime functions to replace the
dangerous datetime.now() pattern across the codebase. All timestamps must be
in UTC to prevent time comparison errors.

Usage:
    from utils.time_utils import get_current_time_utc

    # ❌ DON'T DO THIS - Timezone naive!
    current_time = datetime.now()

    # ✅ DO THIS INSTEAD - Timezone aware!
    current_time = get_current_time_utc()
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def get_current_time_utc() -> datetime:
    """
    Get current time in UTC timezone.

    This is the CORRECT way to get current time for all financial operations
    and time comparisons. Using datetime.now() without timezone
    causes incorrect time comparisons and trade staleness checks.

    Returns:
        Current datetime in UTC timezone

    Examples:
        >>> get_current_time_utc()
        datetime.datetime(2025, 12, 27, 10, 30, tzinfo=datetime.timezone.utc)
    """
    return datetime.now(timezone.utc)


def format_time_ago_utc(timestamp: datetime) -> str:
    """
    Get human-readable time ago string using UTC timestamps.

    Args:
        timestamp: UTC timestamp to calculate time ago

    Returns:
        Human-readable string like "2 hours ago"

    Examples:
        >>> format_time_ago_utc(datetime.now(timezone.utc) - timedelta(hours=2))
        "2 hours ago"
    """
    current_time = get_current_time_utc()
    diff = current_time - timestamp

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
        return f"{diff.seconds} second{'s' if diff.seconds != 1 else ''} ago"


def get_time_delta_seconds_earlier(timestamp1: datetime, timestamp2: datetime) -> float:
    """
    Get time delta in seconds between two UTC timestamps.

    Args:
        timestamp1: First UTC timestamp
        timestamp2: Second UTC timestamp

    Returns:
        Time delta in seconds (positive if timestamp1 < timestamp2)

    Examples:
        >>> t1 = datetime.now(timezone.utc)
        >>> t2 = t1 - timedelta(hours=1)
        >>> get_time_delta_seconds_earlier(t1, t2)
        3600.0
    """
    return (timestamp1 - timestamp2).total_seconds()


def is_timestamp_within_seconds(
    timestamp: datetime, seconds: int, reference_time: datetime = None
) -> bool:
    """
    Check if a UTC timestamp is within a specified time window.

    Args:
        timestamp: UTC timestamp to check
        seconds: Time window in seconds
        reference_time: Reference UTC timestamp (defaults to current time)

    Returns:
        True if timestamp is within the time window

    Examples:
        >>> now = get_current_time_utc()
        >>> recent_time = now - timedelta(minutes=5)
        >>> is_timestamp_within_seconds(recent_time, 300, now)
        True
    """
    if reference_time is None:
        reference_time = get_current_time_utc()

    return (reference_time - timestamp).total_seconds() <= seconds


def is_timestamp_old(timestamp: datetime, max_age_seconds: int = 86400) -> bool:
    """
    Check if a UTC timestamp is older than a maximum age.

    Args:
        timestamp: UTC timestamp to check
        max_age_seconds: Maximum age in seconds (default 24 hours)

    Returns:
        True if timestamp is older than max_age_seconds

    Examples:
        >>> now = get_current_time_utc()
        >>> old_time = now - timedelta(days=1)
        >>> is_timestamp_old(old_time)
        True
    """
    current_time = get_current_time_utc()
    return (current_time - timestamp).total_seconds() > max_age_seconds


def get_time_range_start_end(
    duration_seconds: int, reference_time: datetime = None
) -> tuple[datetime, datetime]:
    """
    Get start and end UTC timestamps for a time range.

    Args:
        duration_seconds: Duration in seconds
        reference_time: Reference UTC timestamp (defaults to current time)

    Returns:
        Tuple of (start_time, end_time) in UTC

    Examples:
        >>> now = get_current_time_utc()
        >>> start, end = get_time_range_start_end(3600, now)
        >>> # Returns (now - 1 hour, now)
    """
    if reference_time is None:
        reference_time = get_current_time_utc()

    start_time = reference_time - timedelta(seconds=duration_seconds)
    end_time = reference_time
    return start_time, end_time
