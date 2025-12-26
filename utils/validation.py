"""
Comprehensive input validation utilities for blockchain trading application.

This module provides robust validation for all external inputs including:
- Wallet addresses and private keys
- Trade amounts and prices
- Condition IDs and transaction data
- Configuration settings
- JSON inputs and API responses

All validation functions follow security best practices:
- Input sanitization and bounds checking
- Type validation and conversion
- Safe error handling with non-sensitive error messages
- Comprehensive logging for debugging
"""

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Union

from eth_utils import is_address
from web3 import Web3

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Custom exception for validation errors"""

    pass


class InputValidator:
    """Comprehensive input validation utility"""

    # Pre-compiled regex patterns for performance
    _WALLET_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
    _PRIVATE_KEY_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")
    _CONDITION_ID_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")
    _HEX_STRING_PATTERN = re.compile(r"^0x[a-fA-F0-9]+$")
    _POSITIVE_NUMBER_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)?$")
    _URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")

    @staticmethod
    def validate_wallet_address(address: str, allow_empty: bool = False) -> str:
        """
        Validate and normalize wallet address

        Args:
            address: Wallet address to validate
            allow_empty: Whether to allow empty addresses

        Returns:
            Normalized checksum address

        Raises:
            ValidationError: If address is invalid
        """
        if not address or address.startswith("#"):
            if allow_empty:
                return ""
            raise ValidationError("Wallet address cannot be empty")

        address = address.strip()

        # Check format first
        if not InputValidator._WALLET_ADDRESS_PATTERN.match(address):
            raise ValidationError(f"Invalid wallet address format: {address}")

        # Check if valid Ethereum address
        if not is_address(address):
            raise ValidationError(f"Invalid Ethereum address: {address}")

        # Convert to checksum address
        try:
            return Web3.to_checksum_address(address)
        except Exception as e:
            raise ValidationError(f"Failed to convert to checksum address: {e}")

    @staticmethod
    def validate_private_key(key: str) -> str:
        """
        Validate private key format

        Args:
            key: Private key to validate

        Returns:
            Validated private key

        Raises:
            ValidationError: If key is invalid
        """
        if not key:
            raise ValidationError("Private key cannot be empty")

        key = key.strip()

        if not InputValidator._PRIVATE_KEY_PATTERN.match(key):
            raise ValidationError(
                "Invalid private key format. Must be 0x followed by 64 hex characters"
            )

        if len(key) != 66:  # 0x + 64 characters
            raise ValidationError(
                f"Invalid private key length: {len(key)} characters (expected 66)"
            )

        return key

    @staticmethod
    def validate_trade_amount(
        amount: Union[int, float, str, Decimal],
        min_amount: float = 0.01,
        max_amount: float = 10000.0,
    ) -> float:
        """
        Validate trade amount

        Args:
            amount: Amount to validate
            min_amount: Minimum allowed amount
            max_amount: Maximum allowed amount

        Returns:
            Validated float amount

        Raises:
            ValidationError: If amount is invalid
        """
        try:
            # Convert to Decimal for precise validation
            if isinstance(amount, str):
                amount = amount.strip()
                if not InputValidator._POSITIVE_NUMBER_PATTERN.match(amount):
                    raise ValidationError(f"Invalid amount format: {amount}")

            decimal_amount = Decimal(str(amount))

            # Validate range
            if decimal_amount <= 0:
                raise ValidationError(f"Amount must be positive: {decimal_amount}")

            if float(decimal_amount) < min_amount:
                raise ValidationError(f"Amount below minimum {min_amount}: {decimal_amount}")

            if float(decimal_amount) > max_amount:
                raise ValidationError(f"Amount above maximum {max_amount}: {decimal_amount}")

            # Convert to float with precision
            return float(decimal_amount.quantize(Decimal("0.000000")))

        except (InvalidOperation, TypeError, ValueError) as e:
            raise ValidationError(f"Invalid amount value: {amount} - {e}")

    @staticmethod
    def validate_price(
        price: Union[int, float, str, Decimal], min_price: float = 0.01, max_price: float = 0.99
    ) -> float:
        """
        Validate price between 0 and 1

        Args:
            price: Price to validate
            min_price: Minimum allowed price
            max_price: Maximum allowed price

        Returns:
            Validated float price

        Raises:
            ValidationError: If price is invalid
        """
        try:
            if isinstance(price, str):
                price = price.strip()
                if not InputValidator._POSITIVE_NUMBER_PATTERN.match(price):
                    raise ValidationError(f"Invalid price format: {price}")

            decimal_price = Decimal(str(price))

            # Validate range
            if not (min_price <= float(decimal_price) <= max_price):
                raise ValidationError(
                    f"Price {decimal_price} out of valid range [{min_price}, {max_price}]"
                )

            # Validate precision
            if decimal_price.as_tuple().exponent < -6:  # More than 6 decimal places
                logger.warning(f"Price {decimal_price} has high precision, rounding to 6 decimals")
                decimal_price = decimal_price.quantize(Decimal("0.000000"))

            return float(decimal_price)

        except (InvalidOperation, TypeError, ValueError) as e:
            raise ValidationError(f"Invalid price value: {price} - {e}")

    @staticmethod
    def validate_condition_id(condition_id: str) -> str:
        """
        Validate condition ID format

        Args:
            condition_id: Condition ID to validate

        Returns:
            Validated condition ID

        Raises:
            ValidationError: If condition ID is invalid
        """
        if not condition_id:
            raise ValidationError("Condition ID cannot be empty")

        condition_id = condition_id.strip()

        if not InputValidator._CONDITION_ID_PATTERN.match(condition_id):
            raise ValidationError(
                "Invalid condition ID format. Must be 0x followed by 64 hex characters"
            )

        return condition_id

    @staticmethod
    def validate_transaction_data(tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate blockchain transaction data

        Args:
            tx_data: Transaction data to validate

        Returns:
            Validated transaction data

        Raises:
            ValidationError: If transaction data is invalid
        """
        required_fields = ["hash", "from", "to", "blockNumber", "timeStamp"]

        # Check required fields
        for field in required_fields:
            if field not in tx_data:
                raise ValidationError(f"Missing required transaction field: {field}")

        # Validate address fields
        tx_data["from"] = InputValidator.validate_wallet_address(tx_data["from"])
        tx_data["to"] = InputValidator.validate_wallet_address(tx_data["to"])

        # Validate hash format
        if not InputValidator._HEX_STRING_PATTERN.match(tx_data["hash"]):
            raise ValidationError(f"Invalid transaction hash format: {tx_data['hash']}")

        # Validate numeric fields
        try:
            tx_data["blockNumber"] = int(tx_data["blockNumber"])
            tx_data["timeStamp"] = int(tx_data["timeStamp"])
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid numeric field: {e}")

        # Validate gas fields if present
        if "gasUsed" in tx_data:
            try:
                gas_used = int(tx_data["gasUsed"])
                if gas_used < 21000:  # Minimum gas for simple transfer
                    raise ValidationError(f"Gas used below minimum: {gas_used}")
                if gas_used > 10000000:  # Reasonable maximum
                    raise ValidationError(f"Gas used above maximum: {gas_used}")
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid gas used value: {e}")

        return tx_data

    @staticmethod
    def sanitize_json_input(json_str: str) -> Dict[str, Any]:
        """
        Sanitize and validate JSON input

        Args:
            json_str: JSON string to sanitize

        Returns:
            Validated dictionary

        Raises:
            ValidationError: If JSON is invalid or contains malicious content
        """
        try:
            # Basic length check
            if len(json_str) > 10000:  # 10KB limit
                raise ValidationError("JSON input too large")

            # Parse JSON
            data = json.loads(json_str)

            # Deep sanitize - remove any suspicious fields
            sanitized = InputValidator._deep_sanitize(data)

            return sanitized

        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format: {e}")
        except Exception as e:
            raise ValidationError(f"Error sanitizing JSON: {e}")

    @staticmethod
    def _deep_sanitize(obj: Any) -> Any:
        """Recursively sanitize object to remove potentially dangerous content"""
        if isinstance(obj, dict):
            return {
                k: InputValidator._deep_sanitize(v)
                for k, v in obj.items()
                if not k.lower().startswith(("script", "eval", "exec", "import", "os", "sys"))
            }
        elif isinstance(obj, list):
            return [InputValidator._deep_sanitize(item) for item in obj]
        elif isinstance(obj, str):
            # Remove potentially dangerous patterns
            if any(
                pattern in obj.lower() for pattern in ["<script", "javascript:", "data:text/html"]
            ):
                return "[SANITIZED]"
            return obj
        else:
            return obj

    @staticmethod
    def validate_config_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration settings

        Args:
            settings: Configuration settings to validate

        Returns:
            Validated settings

        Raises:
            ValidationError: If settings are invalid
        """
        # Validate critical settings
        if "PRIVATE_KEY" not in settings:
            raise ValidationError("Missing PRIVATE_KEY in configuration")

        InputValidator.validate_private_key(settings["PRIVATE_KEY"])

        # Validate numeric settings
        numeric_settings = [
            ("MAX_POSITION_SIZE", 0.01, 100000.0),
            ("MAX_DAILY_LOSS", 0.01, 1000000.0),
            ("MIN_TRADE_AMOUNT", 0.01, 1000.0),
            ("MAX_SLIPPAGE", 0.001, 0.1),
            ("MONITOR_INTERVAL", 5, 300),
            ("MAX_GAS_PRICE", 1, 1000),
            ("GAS_LIMIT", 100000, 2000000),
            ("MAX_CONCURRENT_POSITIONS", 1, 100),
            ("STOP_LOSS_PERCENTAGE", 0.001, 0.5),
            ("TAKE_PROFIT_PERCENTAGE", 0.001, 1.0),
        ]

        for setting_name, min_val, max_val in numeric_settings:
            if setting_name in settings:
                try:
                    value = float(settings[setting_name])
                    if not (min_val <= value <= max_val):
                        raise ValidationError(
                            f"{setting_name} {value} out of valid range [{min_val}, {max_val}]"
                        )
                except (ValueError, TypeError) as e:
                    raise ValidationError(f"Invalid {setting_name} value: {e}")

        # Validate URLs if present
        url_settings = ["POLYGON_RPC_URL", "CLOB_HOST"]
        for url_setting in url_settings:
            if url_setting in settings and settings[url_setting]:
                if not InputValidator._URL_PATTERN.match(settings[url_setting]):
                    raise ValidationError(f"Invalid URL format for {url_setting}")

        return settings

    @staticmethod
    def validate_api_response(response_data: Any, expected_type: type = dict) -> Any:
        """
        Validate API response data

        Args:
            response_data: API response to validate
            expected_type: Expected type of the response

        Returns:
            Validated response data

        Raises:
            ValidationError: If response is invalid
        """
        if not isinstance(response_data, expected_type):
            raise ValidationError(
                f"API response type mismatch. Expected {expected_type.__name__}, got {type(response_data).__name__}"
            )

        if expected_type == dict and not response_data:
            raise ValidationError("Empty API response")

        return response_data

    @staticmethod
    def validate_hex_string(hex_str: str, min_length: int = 2, max_length: int = 66) -> str:
        """
        Validate hexadecimal string

        Args:
            hex_str: Hex string to validate
            min_length: Minimum length including 0x prefix
            max_length: Maximum length including 0x prefix

        Returns:
            Validated hex string

        Raises:
            ValidationError: If hex string is invalid
        """
        if not hex_str:
            raise ValidationError("Hex string cannot be empty")

        hex_str = hex_str.strip()

        if not InputValidator._HEX_STRING_PATTERN.match(hex_str):
            raise ValidationError(f"Invalid hex format: {hex_str}")

        if not (min_length <= len(hex_str) <= max_length):
            raise ValidationError(
                f"Hex string length {len(hex_str)} out of range [{min_length}, {max_length}]"
            )

        return hex_str

    @staticmethod
    def validate_token_amount(
        amount: Union[int, float, str, Decimal],
        decimals: int = 6,
        min_amount: float = 0.0,
        max_amount: float = 10**12,
    ) -> float:
        """
        Validate token amount with decimal precision

        Args:
            amount: Amount to validate
            decimals: Number of decimal places
            min_amount: Minimum allowed amount
            max_amount: Maximum allowed amount

        Returns:
            Validated float amount

        Raises:
            ValidationError: If amount is invalid
        """
        try:
            decimal_amount = Decimal(str(amount))
            quantized = decimal_amount.quantize(Decimal(f"1e-{decimals}"))

            float_amount = float(quantized)

            if not (min_amount <= float_amount <= max_amount):
                raise ValidationError(
                    f"Token amount {float_amount} out of range [{min_amount}, {max_amount}]"
                )

            return float_amount

        except (InvalidOperation, TypeError, ValueError) as e:
            raise ValidationError(f"Invalid token amount: {amount} - {e}")
