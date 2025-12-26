"""
Mock PolygonScan API server for testing.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

import aiohttp
from aiohttp import web

logger = logging.getLogger(__name__)


class PolygonScanMockServer:
    """Mock PolygonScan API server for testing."""

    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.server = None
        self.runner = None
        self.site = None

        # Mock data storage
        self.transactions: Dict[str, List[Dict[str, Any]]] = {}
        self.blocks: Dict[int, Dict[str, Any]] = {}
        self.contracts: Dict[str, Dict[str, Any]] = {}

        # Default responses
        self._setup_default_data()

    def _setup_default_data(self):
        """Set up default mock data."""
        # Add some default transactions for testing
        self.transactions["0x742d35Cc6634C0532925a3b844Bc454e4438f44e"] = [
            {
                "hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "to": "0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a",
                "value": "0",
                "gasUsed": "150000",
                "gasPrice": "50000000000",
                "timeStamp": str(int((datetime.now() - timedelta(seconds=30)).timestamp())),
                "input": "0x1234567890abcdef",
                "blockNumber": "50000000",
            },
            {
                "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "to": "0x8c16f85a4d5f8f23d29e9c7e3d4a3a5a6e4f2b2e",
                "value": "1000000000000000000",  # 1 ETH
                "gasUsed": "21000",
                "gasPrice": "30000000000",
                "timeStamp": str(int((datetime.now() - timedelta(minutes=5)).timestamp())),
                "input": "0x",
                "blockNumber": "50000001",
            },
        ]

        # Add default contract data
        self.contracts["0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a"] = {
            "address": "0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a",
            "name": "Polymarket AMM",
            "abi": [],  # Simplified ABI
        }

    async def handle_txlist(self, request: web.Request) -> web.Response:
        """Handle txlist API calls."""
        params = dict(request.query)

        address = params.get("address")
        startblock = int(params.get("startblock", 0))
        endblock = int(params.get("endblock", 99999999))

        if not address:
            return web.json_response(
                {"status": "0", "message": "Missing address parameter", "result": []}
            )

        # Get transactions for this address
        address_txs = self.transactions.get(address.lower(), [])

        # Filter by block range
        filtered_txs = [
            tx for tx in address_txs if startblock <= int(tx["blockNumber"]) <= endblock
        ]

        # Sort by block number descending (as PolygonScan does)
        filtered_txs.sort(key=lambda x: int(x["blockNumber"]), reverse=True)

        return web.json_response({"status": "1", "message": "OK", "result": filtered_txs})

    async def handle_tokentx(self, request: web.Request) -> web.Response:
        """Handle tokentx API calls."""
        params = dict(request.query)
        address = params.get("address")

        if not address:
            return web.json_response(
                {"status": "0", "message": "Missing address parameter", "result": []}
            )

        # Return mock token transactions
        token_txs = [
            {
                "hash": "0xtoken1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "to": address,
                "value": "1000000000000000000",  # 1 token (assuming 18 decimals)
                "contractAddress": "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",
                "timeStamp": str(int((datetime.now() - timedelta(hours=1)).timestamp())),
                "blockNumber": "50000002",
            }
        ]

        return web.json_response({"status": "1", "message": "OK", "result": token_txs})

    async def handle_get_logs(self, request: web.Request) -> web.Response:
        """Handle getLogs API calls."""
        # Return mock event logs
        logs = [
            {
                "address": "0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a",
                "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"],
                "data": "0x000000000000000000000000742d35Cc6634C0532925a3b844Bc454e4438f44e0000000000000000000000000000000000000000000000000000000000000001",
                "blockNumber": "0x2faf080",
                "timeStamp": str(int((datetime.now() - timedelta(hours=2)).timestamp())),
                "gasPrice": "0xb2d05e00",
                "gasUsed": "0x24a86",
                "logIndex": "0x0",
                "transactionHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "transactionIndex": "0x0",
            }
        ]

        return web.json_response({"status": "1", "message": "OK", "result": logs})

    async def handle_error_response(self, request: web.Request) -> web.Response:
        """Handle error responses for testing."""
        return web.json_response({"status": "0", "message": "Rate limit exceeded", "result": []})

    async def create_app(self) -> web.Application:
        """Create the web application."""
        app = web.Application()

        # Route handlers
        app.router.add_get("/api", self.handle_txlist)
        app.router.add_get("/api/tokentx", self.handle_tokentx)
        app.router.add_get("/api/logs", self.handle_get_logs)
        app.router.add_get("/api/error", self.handle_error_response)

        return app

    async def start(self):
        """Start the mock server."""
        app = await self.create_app()
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        logger.info(f"Mock PolygonScan server started on http://{self.host}:{self.port}")

    async def stop(self):
        """Stop the mock server."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

        logger.info("Mock PolygonScan server stopped")

    def add_transaction(self, address: str, transaction: Dict[str, Any]):
        """Add a transaction to the mock data."""
        address = address.lower()
        if address not in self.transactions:
            self.transactions[address] = []

        self.transactions[address].append(transaction)

    def clear_transactions(self, address: str = None):
        """Clear transactions for testing."""
        if address:
            self.transactions.pop(address.lower(), None)
        else:
            self.transactions.clear()

    def set_rate_limit_mode(self, enabled: bool = True):
        """Enable/disable rate limiting simulation."""
        # In a real implementation, this would modify response behavior
        self.rate_limiting_enabled = enabled

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


class AsyncPolygonScanClient:
    """Async client for interacting with mock PolygonScan server."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_transactions(
        self, address: str, api_key: str = "test", start_block: int = 0, end_block: int = 99999999
    ) -> List[Dict[str, Any]]:
        """Get transactions for an address."""
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "sort": "desc",
            "apikey": api_key,
        }

        async with self.session.get(f"{self.base_url}/api", params=params) as response:
            data = await response.json()

            if data.get("status") == "1":
                return data.get("result", [])
            else:
                raise Exception(f"PolygonScan API error: {data.get('message')}")

    async def simulate_rate_limit(self) -> None:
        """Simulate hitting rate limit."""
        async with self.session.get(f"{self.base_url}/api/error") as response:
            data = await response.json()
            raise Exception(f"Rate limit: {data.get('message')}")


# Example usage and test helpers
async def create_test_server():
    """Create and start a test server for integration tests."""
    server = PolygonScanMockServer()
    await server.start()
    return server


if __name__ == "__main__":
    # Run standalone server for testing
    async def main():
        server = PolygonScanMockServer()
        try:
            await server.start()
            print("Mock server running. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await server.stop()

    asyncio.run(main())
