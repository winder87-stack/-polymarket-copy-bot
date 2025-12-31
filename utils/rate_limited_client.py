"""Rate-limited API clients for external services."""

import asyncio
import logging
from asyncio import Lock, Semaphore
from time import time
from typing import Any, Dict, List, Optional

import aiohttp

from core.exceptions import APIError, PolygonscanError, RateLimitError

logger = logging.getLogger(__name__)


class RateLimitedPolygonscanClient:
    """Polygonscan client with proper rate limiting for blockchain transaction queries."""

    # Polygonscan free tier: 5 calls/second
    CALLS_PER_SECOND = 5

    def __init__(self, api_key: str) -> None:
        """
        Initialize the rate-limited Polygonscan client.

        Args:
            api_key: Polygonscan API key for authentication
        """
        self.api_key = api_key
        self._semaphore: Semaphore = Semaphore(1)  # Only 1 concurrent request
        self._lock: Lock = Lock()
        self._last_call_time: float = 0.0
        self._min_interval: float = 1.0 / self.CALLS_PER_SECOND

    async def _wait_for_rate_limit(self) -> None:
        """
        Ensure we don't exceed rate limits by waiting if necessary.

        This method implements rate limiting by tracking the time between API calls
        and sleeping if the minimum interval hasn't elapsed.
        """
        async with self._lock:
            now: float = time()
            elapsed: float = now - self._last_call_time
            if elapsed < self._min_interval:
                wait_time: float = self._min_interval - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            self._last_call_time = time()

    async def get_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        max_transactions: int = 10000,
    ) -> List[Dict[str, Any]]:
        """
        Fetch transactions for a wallet address with rate limiting.

        Args:
            address: Wallet address to query transactions for
            start_block: Starting block number (optional)
            end_block: Ending block number (optional)
            max_transactions: Maximum number of transactions to return

        Returns:
            List of transaction dictionaries from Polygonscan API

        Raises:
            PolygonscanError: If the API returns an error
            RateLimitError: If rate limit is exceeded
        """
        async with self._semaphore:
            await self._wait_for_rate_limit()

            try:
                return await self._fetch_transactions(
                    address, start_block, end_block, max_transactions
                )
            except RateLimitError:
                # If rate limited, wait longer and retry once
                logger.warning("Rate limited, waiting 60s and retrying...")
                await asyncio.sleep(60)
                await self._wait_for_rate_limit()
                return await self._fetch_transactions(
                    address, start_block, end_block, max_transactions
                )

    async def _fetch_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        max_transactions: int = 10000,
    ) -> List[Dict[str, Any]]:
        """
        Make the actual API call to Polygonscan.

        Args:
            address: Wallet address to query
            start_block: Starting block number
            end_block: Ending block number
            max_transactions: Maximum transactions to return

        Returns:
            List of transaction data

        Raises:
            PolygonscanError: For API errors
            RateLimitError: For rate limiting
        """
        url = "https://api.polygonscan.com/v2/api"
        headers = {
            "User-Agent": "Polymarket-Copy-Bot/1.0",
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }

        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block or 0,
            "endblock": end_block or 99999999,
            "sort": "desc",
        }

        timeout = aiohttp.ClientTimeout(total=15, connect=5)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 429:
                    raise RateLimitError("Polygonscan rate limit exceeded")
                elif response.status != 200:
                    raise PolygonscanError(
                        f"Polygonscan API error: HTTP {response.status}"
                    )

                data = await response.json()

                # Check for API-level errors
                if data.get("status") == "0":
                    error_msg = data.get("message", "Unknown error")
                    if "rate limit" in error_msg.lower():
                        raise RateLimitError(
                            f"Polygonscan API rate limited: {error_msg}"
                        )
                    else:
                        raise PolygonscanError(f"Polygonscan API error: {error_msg}")

                # Handle both v1 and v2 API response formats
                if (
                    data.get("status") == "1" and data.get("message") == "OK"
                ) or data.get("status") == "success":
                    transactions = data.get("result", [])

                    # Handle different response structures
                    if (
                        isinstance(transactions, dict)
                        and "transactions" in transactions
                    ):
                        transactions = transactions["transactions"]

                    if not isinstance(transactions, list):
                        raise PolygonscanError(
                            f"Unexpected response format: {type(transactions)}"
                        )

                    # Limit transactions for performance
                    if len(transactions) > max_transactions:
                        transactions = transactions[:max_transactions]

                    return transactions
                else:
                    raise PolygonscanError(f"Unexpected API response: {data}")

    async def get_transactions_batch(
        self,
        addresses: list[str],
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        max_transactions: int = 10000,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Fetch transactions for multiple wallet addresses sequentially.

        This method processes addresses one by one to respect rate limits,
        rather than making concurrent requests which would violate API limits.

        Args:
            addresses: List of wallet addresses to query
            start_block: Starting block number for all queries
            end_block: Ending block number for all queries
            max_transactions: Maximum transactions per address

        Returns:
            Dictionary mapping addresses to their transaction lists
        """
        results: dict[str, list[dict[str, Any]]] = {}
        for address in addresses:
            try:
                logger.debug(f"Fetching transactions for {address}")
                txs = await self.get_transactions(
                    address, start_block, end_block, max_transactions
                )
                results[address] = txs
                logger.debug(f"Retrieved {len(txs)} transactions for {address}")
            except Exception as e:
                logger.error(f"Failed to fetch transactions for {address}: {e}")
                results[address] = []
        return results


class RateLimitedPolymarketClient:
    """Polymarket CLOB client with proper rate limiting."""

    # Polymarket API: 10 calls/second recommended
    CALLS_PER_SECOND = 10

    def __init__(self, host: str, private_key: str) -> None:
        """
        Initialize the rate-limited Polymarket client.

        Args:
            host: Polymarket API host URL
            private_key: Private key for authentication
        """
        self.host = host
        self.private_key = private_key
        self._semaphore: Semaphore = Semaphore(1)  # Only 1 concurrent request
        self._lock: Lock = Lock()
        self._last_call_time: float = 0.0
        self._min_interval: float = 1.0 / self.CALLS_PER_SECOND

    async def _wait_for_rate_limit(self) -> None:
        """
        Ensure we don't exceed rate limits by waiting if necessary.

        This method implements rate limiting by tracking the time between API calls
        and sleeping if the minimum interval hasn't elapsed.
        """
        async with self._lock:
            now: float = time()
            elapsed: float = now - self._last_call_time
            if elapsed < self._min_interval:
                wait_time: float = self._min_interval - elapsed
                logger.debug(f"Rate limiting Polymarket API: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            self._last_call_time = time()

    async def make_request(self, method: str, **kwargs: Any) -> Any:
        """
        Make a rate-limited request to the Polymarket CLOB API.

        Args:
            method: API method name (get_balance, get_market, etc.)
            **kwargs: Additional arguments for the specific method

        Returns:
            API response data

        Raises:
            APIError: For API failures or unknown methods
        """
        async with self._semaphore:
            await self._wait_for_rate_limit()

            try:
                # Import here to avoid circular imports
                from py_clob_client.client import ClobClient
                from py_clob_client.constants import POLYGON

                client = ClobClient(
                    host=self.host, key=self.private_key, chain_id=POLYGON
                )

                # Map method names to client methods
                if method == "get_balance":
                    return client.get_balance()
                elif method == "get_market":
                    return client.get_market(kwargs["condition_id"])
                elif method == "get_markets":
                    return client.get_markets()
                elif method == "get_orders":
                    return client.get_orders()
                elif method == "post_order":
                    return client.post_order(kwargs["order"])
                elif method == "cancel_order":
                    return client.cancel(kwargs["order_id"])
                elif method == "get_trades":
                    return client.get_trades(**kwargs)
                elif method == "get_order_book":
                    return client.get_order_book(kwargs["condition_id"])
                else:
                    raise APIError(f"Unknown Polymarket API method: {method}")

            except Exception as e:
                logger.error(f"Polymarket API error for {method}: {e}")
                raise APIError(f"Polymarket API failed: {e}") from e
