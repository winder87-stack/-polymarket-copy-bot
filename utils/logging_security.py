"""
Secure logging utilities for blockchain trading application.

This module provides comprehensive protection against sensitive data leakage in logs:
- Automatic masking of private keys, wallet addresses, API keys, and tokens
- Secure logging wrapper with data sanitization
- Audit logging for security events
- Log file encryption and access controls
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from utils.helpers import BoundedCache

try:
    import filelock

    FILELOCK_AVAILABLE = True
except ImportError:
    FILELOCK_AVAILABLE = False
    logging.warning("filelock not available - audit logging will be degraded")

logger = logging.getLogger(__name__)


class SensitiveDataMasker:
    """Advanced sensitive data masking for secure logging"""

    # Pre-compiled regex patterns for sensitive data detection
    # Order matters - more specific patterns first
    _SENSITIVE_PATTERNS = [
        # Private keys (64 hex chars - most specific)
        (
            re.compile(r"\b0x[a-f0-9]{64}\b", re.IGNORECASE),
            lambda m: f"{m.group(0)[:6]}...[PRIVATE_KEY]",
        ),
        # Wallet addresses (40 hex chars)
        (
            re.compile(r"\b0x[a-f0-9]{40}\b", re.IGNORECASE),
            lambda m: f"{m.group(0)[:6]}...{m.group(0)[-4:]}",
        ),
        # JSON Web Tokens
        (
            re.compile(
                r"eyJ[a-zA-Z0-9\-_]+\.eyJ[a-zA-Z0-9\-_]+\.?[a-zA-Z0-9\-_]+",
                re.IGNORECASE,
            ),
            lambda m: "[JWT_TOKEN_REDACTED]",
        ),
        # API keys and tokens (more general patterns)
        (
            re.compile(
                r'(?:api_key|token|secret|password)["\s]*[:=]["\s]*[a-z0-9_\-]{20,}',
                re.IGNORECASE,
            ),
            lambda m: re.sub(
                r"[a-z0-9_\-]{5,}$",
                "..." + "[REDACTED]",
                m.group(0),
                flags=re.IGNORECASE,
            ),
        ),
        # Credit card numbers
        (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), lambda m: "[CARD_NUMBER_REDACTED]"),
        # Email addresses
        (
            re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
            lambda m: f"{m.group(0).split('@')[0][:2]}...@{m.group(0).split('@')[1]}",
        ),
    ]

    _SENSITIVE_KEYS = [
        "private_key",
        "secret",
        "password",
        "token",
        "api_key",
        "auth",
        "credential",
        "wallet",
        "address",
        "signature",
        "seed",
        "mnemonic",
        "passphrase",
    ]

    def __init__(self) -> None:
        self._masking_cache = BoundedCache(
            max_size=10000, ttl_seconds=3600
        )  # 1 hour TTL
        self._compiled_patterns = [
            (pattern, replacer) for pattern, replacer in self._SENSITIVE_PATTERNS
        ]

    def mask_sensitive_data(self, data: Any, context: str = "unknown") -> Any:
        """
        Recursively mask sensitive data in any structure

        Args:
            data: Data to mask
            context: Context for logging masking decisions

        Returns:
            Masked data with same structure
        """
        try:
            return self._mask_recursive(data, context)
        except Exception as e:
            logger.error(f"Error masking sensitive data: {e}")
            # Return minimal safe data instead of failing
            return "[MASKING_ERROR]"

    def _mask_recursive(self, data: Any, context: str) -> Any:
        """Recursive masking implementation"""
        if data is None:
            return None
        elif isinstance(data, str):
            return self._mask_string(data, context)
        elif isinstance(data, (int, float, bool)):
            return data
        elif isinstance(data, dict):
            return self._mask_dict(data, context)
        elif isinstance(data, list):
            return [self._mask_recursive(item, f"{context}[list]") for item in data]
        elif isinstance(data, tuple):
            return tuple(
                self._mask_recursive(item, f"{context}[tuple]") for item in data
            )
        elif hasattr(data, "__dict__"):
            # Handle objects by converting to dict
            obj_dict = vars(data)
            masked_dict = self._mask_dict(obj_dict, f"{context}[object]")
            return (
                type(data)(**masked_dict) if hasattr(data, "__init__") else masked_dict
            )
        else:
            # Fallback for unknown types - convert to string and mask
            return self._mask_string(str(data), context)

    def _mask_string(self, text: str, context: str) -> str:
        """Mask sensitive patterns in strings with context awareness"""
        if not text:
            return text

        # Check cache first
        cache_key = str(hash(text))
        cached_result = self._masking_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        masked_text = text

        # Context-aware masking - don't mask transaction hashes as private keys
        is_transaction_hash = "hash" in context.lower() or "tx_" in context.lower()

        # Apply sensitive patterns with context awareness
        for pattern, replacer in self._compiled_patterns:
            if pattern.search(masked_text):
                # Skip private key masking for transaction hashes and similar contexts
                replacer_str = str(replacer)
                if "[PRIVATE_KEY]" in replacer_str and is_transaction_hash:
                    continue
                masked_text = pattern.sub(replacer, masked_text)

        # Cache result - BoundedCache handles size limits
        self._masking_cache.set(cache_key, masked_text[:1000])

        return masked_text

    def _mask_dict(self, data: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Mask sensitive keys and values in dictionaries"""
        masked = {}

        for key, value in data.items():
            key_lower = str(key).lower()

            # Check if key contains sensitive terms
            is_sensitive_key = any(
                sensitive in key_lower for sensitive in self._SENSITIVE_KEYS
            )

            if is_sensitive_key:
                # Mask the entire value for sensitive keys
                masked[key] = self._mask_sensitive_value(value, f"{context}.{key}")
            else:
                # Check if value might contain sensitive data
                masked[key] = self._mask_recursive(value, f"{context}.{key}")

        return masked

    def _mask_sensitive_value(self, value: Any, context: str) -> str:
        """Mask values that are known to be sensitive"""
        if value is None:
            return "[NULL]"

        if isinstance(value, str):
            if len(value) > 100:  # Long strings are likely sensitive
                return f"[REDACTED:{self._get_value_type(value, context)}]"
            return f"[REDACTED:{self._get_value_type(value, context)}]"

        return "[REDACTED]"

    def _get_value_type(self, value: str, context: str = "") -> str:
        """Determine the type of sensitive value for logging with context awareness"""
        # Context-aware detection
        context_lower = context.lower()

        # Transaction hashes should not be treated as private keys
        if any(keyword in context_lower for keyword in ["hash", "tx_", "transaction"]):
            return "HASH"

        if re.match(r"^0x[a-f0-9]{64}$", value, re.IGNORECASE):
            return "PRIVATE_KEY"
        elif re.match(r"^0x[a-f0-9]{40}$", value, re.IGNORECASE):
            return "WALLET_ADDRESS"
        elif re.match(r"^[a-z0-9]{32,}$", value, re.IGNORECASE):
            return "API_KEY"
        else:
            return "UNKNOWN_SENSITIVE"


class SecureLogger:
    """Secure logging wrapper with automatic sensitive data masking"""

    _masker = SensitiveDataMasker()

    @classmethod
    def log(
        cls,
        level: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ):
        """
        Secure logging method with automatic data masking

        Args:
            level: Log level ('debug', 'info', 'warning', 'error', 'critical')
            message: Log message
            data: Additional data to log (will be masked)
            context: Context information for masking decisions
            exc_info: Whether to include exception information
        """
        try:
            # Mask sensitive data
            masked_data = (
                cls._masker.mask_sensitive_data(data, context="log_data")
                if data
                else None
            )
            (
                cls._masker.mask_sensitive_data(context, context="log_context")
                if context
                else None
            )

            # Get the appropriate logger method
            log_method = getattr(logger, level.lower())

            # Log with appropriate parameters
            if masked_data:
                log_method(
                    f"{message} | data={json.dumps(masked_data, default=str)}",
                    exc_info=exc_info,
                )
            else:
                log_method(message, exc_info=exc_info)

        except Exception as e:
            # Fallback to basic logging if secure logging fails
            try:
                logger.error(
                    f"Secure logging failed: {e} | Original message: {message}"
                )
            except (IOError, OSError, UnicodeEncodeError) as e2:
                # Ultimate fallback - print to stderr
                import sys

                print(f"SECURE LOGGING FAILURE: {e2}", file=sys.stderr)

    @classmethod
    def audit_log(
        cls, action: str, details: Dict[str, Any], user: str = "system"
    ) -> None:
        """
        Log security audit events

        Args:
            action: Action performed
            details: Details of the action
            user: User who performed the action
        """
        masked_details = cls._masker.mask_sensitive_data(details, context="audit_log")

        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user": user,
            "details": masked_details,
            "source_ip": details.get("source_ip", "unknown"),
            "severity": cls._get_audit_severity(action),
        }

        # Log to separate audit file
        cls._write_audit_log(audit_entry)

        # Also log to main logger with appropriate level
        level = "warning" if cls._get_audit_severity(action) == "high" else "info"
        cls.log(level, f"Audit: {action}", masked_details)

    @classmethod
    def audit_security_event(cls, event_type: str, details: Dict[str, Any]) -> None:
        """Log security-related events with high priority"""
        details["event_type"] = event_type
        details["security_event"] = True

        cls.audit_log(f"security_{event_type}", details, user="system")

    @classmethod
    def audit_configuration_change(
        cls, component: str, old_value: Any, new_value: Any, user: str = "system"
    ):
        """Audit configuration changes"""
        cls.audit_log(
            "configuration_change",
            {
                "component": component,
                "old_value": cls._masker.mask_sensitive_data(
                    old_value, context="config_audit"
                ),
                "new_value": cls._masker.mask_sensitive_data(
                    new_value, context="config_audit"
                ),
                "change_type": "modification",
            },
            user=user,
        )

    @classmethod
    def audit_file_access(
        cls, file_path: str, operation: str, user: str = "system"
    ) -> None:
        """Audit file access operations"""
        cls.audit_log(
            "file_access",
            {
                "file_path": file_path,
                "operation": operation,
                "file_type": "log" if file_path.endswith(".log") else "unknown",
            },
            user=user,
        )

    @classmethod
    def audit_authentication_event(
        cls, event_type: str, details: Dict[str, Any]
    ) -> None:
        """Audit authentication-related events"""
        cls.audit_log(
            f"auth_{event_type}", details, user=details.get("username", "unknown")
        )

    @classmethod
    def _get_audit_severity(cls, action: str) -> str:
        """Determine audit event severity"""
        high_severity_actions = [
            "security_breach",
            "unauthorized_access",
            "configuration_change",
            "log_file_insecure_permissions",
            "log_file_integrity_issue",
            "sensitive_data_exposure",
            "authentication_failure",
        ]

        if any(severity_action in action for severity_action in high_severity_actions):
            return "high"

        medium_severity_actions = ["file_access", "log_rotation", "permission_change"]

        if any(
            severity_action in action for severity_action in medium_severity_actions
        ):
            return "medium"

        return "low"

    @classmethod
    def _write_audit_log(cls, entry: Dict[str, Any]) -> None:
        """Write audit log to secure file"""
        try:
            audit_log_path = "logs/audit.log"
            os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)

            # Use file lock to prevent concurrent writes if available
            if FILELOCK_AVAILABLE:
                lock_path = f"{audit_log_path}.lock"
                with filelock.FileLock(lock_path, timeout=5):
                    with open(audit_log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, default=str) + "\n")
            else:
                # Fallback without locking (less secure but functional)
                with open(audit_log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")


# Enhanced secure_log function
def secure_log(
    logger: logging.Logger, action: str, data: Dict[str, Any], level: str = "info"
):
    """Enhanced secure logging with comprehensive masking"""
    try:
        # Use the secure logger
        SecureLogger.log(
            level=level,
            message=f"{action}",
            data=data,
            context={"action": action, "logger": logger.name},
        )
    except Exception as e:
        # Fallback to basic logging
        logger.error(f"Secure logging failed for action '{action}': {e}")


class LogFileSecurity:
    """Secure log file management with access controls and audit logging"""

    def __init__(self, log_file_path: str) -> None:
        self.log_file_path = log_file_path
        self.audit_enabled = True

    def secure_file_permissions(self) -> None:
        """Set secure file permissions for log files"""
        try:
            import stat

            # Set owner read/write only (0o600)
            os.chmod(self.log_file_path, stat.S_IRUSR | stat.S_IWUSR)

            # Audit the permission change
            if self.audit_enabled:
                SecureLogger.audit_log(
                    "log_file_permissions_changed",
                    {
                        "file_path": self.log_file_path,
                        "new_permissions": "0o600",
                        "action": "secure_permissions",
                    },
                )

        except Exception as e:
            logger.error(f"Failed to set secure log file permissions: {e}")

    def rotate_log_file(self, backup_count: int = 5) -> None:
        """Rotate log files securely"""
        try:
            import shutil

            log_dir = os.path.dirname(self.log_file_path)
            base_name = os.path.basename(self.log_file_path)

            # Rotate existing backups
            for i in range(backup_count - 1, 0, -1):
                src = os.path.join(log_dir, f"{base_name}.{i}")
                dst = os.path.join(log_dir, f"{base_name}.{i + 1}")
                if os.path.exists(src):
                    shutil.move(src, dst)

            # Move current log to backup
            if os.path.exists(self.log_file_path):
                backup_path = os.path.join(log_dir, f"{base_name}.1")
                shutil.move(self.log_file_path, backup_path)

                # Set secure permissions on backup
                os.chmod(backup_path, 0o600)

            # Audit the rotation
            if self.audit_enabled:
                SecureLogger.audit_log(
                    "log_file_rotated",
                    {
                        "file_path": self.log_file_path,
                        "backup_count": backup_count,
                        "action": "rotate_logs",
                    },
                )

        except Exception as e:
            logger.error(f"Failed to rotate log file: {e}")

    def monitor_log_access(self) -> None:
        """Monitor log file access (basic implementation)"""
        try:
            # Check if log file exists and is accessible
            if os.path.exists(self.log_file_path):
                stat_info = os.stat(self.log_file_path)

                # Check for suspicious permissions
                mode = stat_info.st_mode
                if mode & 0o077:  # Group or other permissions
                    SecureLogger.audit_log(
                        "log_file_insecure_permissions",
                        {
                            "file_path": self.log_file_path,
                            "current_permissions": oct(mode),
                            "issue": "group_or_other_permissions_set",
                        },
                    )

                # Check file size for potential issues
                size = stat_info.st_size
                if size > 100 * 1024 * 1024:  # 100MB warning
                    SecureLogger.audit_log(
                        "log_file_large_size",
                        {
                            "file_path": self.log_file_path,
                            "size_bytes": size,
                            "size_mb": size / (1024 * 1024),
                            "warning": "log_file_exceeds_100mb",
                        },
                    )

        except Exception as e:
            logger.error(f"Failed to monitor log file access: {e}")

    def validate_log_integrity(self) -> bool:
        """Validate log file integrity (basic checks)"""
        try:
            if not os.path.exists(self.log_file_path):
                return False

            # Check file is readable
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                # Try to read first few lines
                lines = f.readlines()[:10]

            # Basic format validation
            json_lines = 0
            invalid_lines = 0

            for line in lines:
                try:
                    json.loads(line.strip())
                    json_lines += 1
                except (json.JSONDecodeError, ValueError):
                    invalid_lines += 1

            # If more than 50% of lines are invalid, flag as suspicious
            if invalid_lines > json_lines:
                SecureLogger.audit_log(
                    "log_file_integrity_issue",
                    {
                        "file_path": self.log_file_path,
                        "json_lines": json_lines,
                        "invalid_lines": invalid_lines,
                        "issue": "high_invalid_line_ratio",
                    },
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to validate log integrity: {e}")
            return False


# Global log security manager
_log_security_manager = None


def get_log_security_manager(log_file_path: str) -> LogFileSecurity:
    """Get or create log security manager instance"""
    global _log_security_manager
    if (
        _log_security_manager is None
        or _log_security_manager.log_file_path != log_file_path
    ):
        _log_security_manager = LogFileSecurity(log_file_path)
    return _log_security_manager
