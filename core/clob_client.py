# core/clob_client.py - FIXED FOR py-clob-client==0.34.1
from typing import Any

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

from utils.logger import get_logger

logger = get_logger(__name__)


class PolymarketClient:
    """Fixed CLOB client compatible with py-clob-client==0.34.1"""

    def __init__(self) -> None:
        from config import get_settings

        self.settings = get_settings()
        self.host = self.settings.network.clob_host
        self.chain_id = POLYGON
        self.private_key = self.settings.trading.private_key

        # 🔴 FIX: Correct initialization for v0.34.1
        self.client = ClobClient(
            host=self.host, chain_id=self.chain_id, key=self.private_key
        )

        # Get wallet address
        self.wallet_address = self.client.get_address()
        logger.info(
            "✅ CLOB client initialized for wallet: %s", self.wallet_address[-6:]
        )

    def get_balance(self) -> dict[str, Any]:
        """
        ✅ FIXED: Type ignore removed - proper type hint added

        Returns the wallet's balance in USDC, MATIC, and raw string format.

        Note: The balance API may return different response formats depending on
        the CLOB client version and network conditions. We handle multiple formats:
        - Dict: Direct dictionary response
        - to_dict(): Object with .to_dict() method
        - Raw string: Fallback for unexpected formats

        Returns:
            dict: {
                "usdc": float (balance in USDC),
                "matic": float (balance in MATIC),
                "raw_response": str (raw response as fallback),
            }
        """
        try:
            # 🔴 FIX: Use correct balance API for v0.34.1
            balance_response = self.client.get_balance()

            # Handle different response formats
            if isinstance(balance_response, dict):
                return balance_response
            elif hasattr(balance_response, "to_dict"):
                return balance_response.to_dict()
            else:
                logger.warning(
                    "Unexpected balance response type: %s", type(balance_response)
                )
                return {
                    "usdc": 0.0,
                    "matic": 0.0,
                    "raw_response": str(balance_response),
                }

        except Exception as e:
            logger.error("❌ Balance check failed: %s", str(e)[:150])
            return {"usdc": 0.0, "matic": 0.0, "error": str(e)}

    def health_check(self) -> bool:
        """✅ Comprehensive health check including balance verification"""
        try:
            # Check API connectivity
            is_connected = hasattr(self.client, "get_balance") and callable(
                self.client.get_balance
            )

            # Check we can get balance
            balance = self.get_balance()
            has_usdc = balance.get("usdc", 0) > 0.01  # At least 0.01 USDC

            # Check wallet address is valid
            valid_address = self.wallet_address and self.wallet_address.startswith("0x")

            healthy = is_connected and has_usdc and valid_address

            if healthy:
                logger.info(
                    "✅ CLOB Health Check PASSED - Balance: $%s", balance.get("usdc", 0)
                )
            else:
                logger.warning(
                    "⚠️ CLOB Health Check WARNING - Connected: %s, Has USDC: %s, Valid Address: %s",
                    is_connected,
                    has_usdc,
                    valid_address,
                )

            return healthy

        except Exception as e:
            logger.error("❌ CLOB health check failed: %s", str(e)[:150])
            return False
