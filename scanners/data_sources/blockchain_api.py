import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from config.scanner_config import ScannerConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class BlockchainAPI:
    """Production-grade blockchain verification API client using QuickNode RPC"""

    def __init__(self, config: ScannerConfig) -> None:
        self.config = config
        self.rpc_url = config.POLYGON_RPC_URL  # Use your QuickNode URL
        self.web3 = Web3(
            Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 30})
        )

        # Add POA middleware for Polygon
        self.web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not self.web3.is_connected():
            logger.error("❌ Failed to connect to QuickNode RPC endpoint")
            raise ConnectionError("Cannot connect to Polygon blockchain via QuickNode")

        logger.info(
            f"✅ Connected to Polygon blockchain via QuickNode: {self.rpc_url[:40]}..."
        )

        self.last_request_time = 0
        self.rate_limit_delay = (
            0.1  # 10 requests per second limit (adjust based on your QuickNode plan)
        )
        self.max_retries = 3

    def _respect_rate_limits(self) -> None:
        """Enforce rate limiting to prevent RPC bans"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    async def get_wallet_transactions(
        self,
        wallet_address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent transactions for a wallet using event filtering"""
        try:
            self._respect_rate_limits()

            # Get current block number if not provided
            current_block = self.web3.eth.block_number
            if end_block is None:
                end_block = current_block
            if start_block is None:
                start_block = max(
                    0, end_block - 1000
                )  # Look back 1000 blocks (~2 hours)

            # Get transaction count to estimate activity
            tx_count = self.web3.eth.get_transaction_count(wallet_address)
            logger.debug(f"Wallet {wallet_address[:8]} has {tx_count} transactions")

            # This is a simplified version - in production you'd want to use event filters
            # For now, we'll return basic transaction data
            return await self._get_recent_transactions(
                wallet_address, start_block, end_block
            )

        except Exception as e:
            logger.error(f"Failed to get wallet transactions for {wallet_address}: {e}")
            return []

    async def _get_recent_transactions(
        self, wallet_address: str, start_block: int, end_block: int
    ) -> List[Dict[str, Any]]:
        """Get recent transactions by scanning blocks (simplified for production)"""
        transactions = []

        try:
            # Scan recent blocks for transactions involving this wallet
            for block_num in range(
                end_block, max(start_block, end_block - 50), -1
            ):  # Scan last 50 blocks
                self._respect_rate_limits()
                block = self.web3.eth.get_block(block_num, full_transactions=True)

                for tx in block.transactions:
                    if hasattr(tx, "hash"):
                        tx_hash = tx.hash.hex()
                        tx_from = tx["from"].lower() if "from" in tx else ""
                        tx_to = tx["to"].lower() if "to" in tx and tx["to"] else ""

                        if (tx_from == wallet_address.lower()) or (
                            tx_to == wallet_address.lower()
                        ):
                            transactions.append(
                                {
                                    "hash": tx_hash,
                                    "from": tx_from,
                                    "to": tx_to,
                                    "value": tx.value / 1e18
                                    if hasattr(tx, "value")
                                    else 0,
                                    "gasPrice": tx.gasPrice
                                    if hasattr(tx, "gasPrice")
                                    else 0,
                                    "blockNumber": block_num,
                                    "timestamp": block.timestamp,
                                    "gasUsed": 0,  # Would need receipt for this
                                    "status": 1,  # Assume success, would need receipt for actual status
                                }
                            )

                if len(transactions) >= 100:  # Limit results
                    break

            return transactions

        except Exception as e:
            logger.error(f"Error scanning blocks for transactions: {e}")
            return []

    async def verify_trade_on_chain(
        self, wallet_address: str, trade_hash: str, contract_address: str
    ) -> Dict[str, Any]:
        """Verify a specific trade occurred on-chain by transaction hash"""
        try:
            self._respect_rate_limits()

            # Get transaction receipt
            tx_receipt = self.web3.eth.get_transaction_receipt(trade_hash)

            if not tx_receipt:
                logger.warning(f"Transaction {trade_hash} not found on chain")
                return {
                    "verified": False,
                    "status": "not_found",
                    "error": "tx_not_found",
                }

            # Get transaction details
            tx = self.web3.eth.get_transaction(trade_hash)

            # Verify the wallet was involved (sender or recipient)
            wallet_lower = wallet_address.lower()
            tx_from = tx["from"].lower()
            tx_to = tx["to"].lower() if tx["to"] else ""

            involved = (tx_from == wallet_lower) or (tx_to == wallet_lower)

            # Verify it interacted with the expected contract
            contract_match = (
                tx_to == contract_address.lower() if contract_address else True
            )

            # Get transaction status (success/failure)
            status = tx_receipt.status if hasattr(tx_receipt, "status") else 1

            return {
                "verified": involved and contract_match and (status == 1),
                "status": (
                    "confirmed"
                    if involved and contract_match and (status == 1)
                    else "failed"
                ),
                "transaction_details": {
                    "hash": trade_hash,
                    "from": tx_from,
                    "to": tx_to,
                    "value": tx.value / 1e18,
                    "gas_used": tx_receipt.gasUsed,
                    "block_number": tx_receipt.blockNumber,
                    "timestamp": self.web3.eth.get_block(
                        tx_receipt.blockNumber
                    ).timestamp,
                    "status": status,
                },
                "involved": involved,
                "contract_match": contract_match,
                "success": status == 1,
            }

        except Exception as e:
            logger.error(f"Failed to verify trade {trade_hash} on chain: {e}")
            return {"verified": False, "status": "verification_error", "error": str(e)}

    async def detect_wash_trading_patterns(
        self, wallet_address: str, time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Detect potential wash trading patterns by analyzing on-chain transaction patterns
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (time_window_hours * 3600)

            # Get recent transactions
            transactions = await self.get_wallet_transactions(wallet_address)

            # Filter by time window
            recent_txs = []
            for tx in transactions:
                try:
                    tx_time = tx.get("timestamp", 0)
                    if tx_time > cutoff_time:
                        recent_txs.append(tx)
                except (ValueError, TypeError, AttributeError):
                    continue

            if len(recent_txs) < 5:
                return {"wash_trading_score": 0.0, "evidence": "insufficient_data"}

            # Analyze patterns
            wash_indicators = {
                "rapid_round_trips": 0,
                "identical_amounts": 0,
                "self_transactions": 0,
                "suspicious_contracts": 0,
            }

            # Sort by timestamp
            recent_txs.sort(key=lambda x: x.get("timestamp", 0))

            # Check for rapid round trips
            for i in range(len(recent_txs) - 1):
                tx1 = recent_txs[i]
                tx2 = recent_txs[i + 1]

                time_diff = tx2.get("timestamp", 0) - tx1.get("timestamp", 0)

                # Look for transactions within 5 minutes
                if 0 < time_diff < 300:
                    amount1 = tx1.get("value", 0)
                    amount2 = tx2.get("value", 0)

                    if amount1 > 0 and amount2 > 0:
                        ratio = min(amount1, amount2) / max(amount1, amount2)
                        if ratio > 0.95:  # Within 5%
                            wash_indicators["rapid_round_trips"] += 1

            # Check for identical amounts
            amounts = [
                round(tx.get("value", 0), 6)
                for tx in recent_txs
                if tx.get("value", 0) > 0
            ]
            from collections import Counter

            amount_counts = Counter(amounts)
            identical_count = sum(
                count
                for amount, count in amount_counts.items()
                if count > 1 and count < len(recent_txs)
            )
            wash_indicators["identical_amounts"] = identical_count

            # Check for self-transactions
            for tx in recent_txs:
                tx_from = tx.get("from", "").lower()
                tx_to = tx.get("to", "").lower()
                if tx_from == tx_to and tx_from == wallet_address.lower():
                    wash_indicators["self_transactions"] += 1

            # Calculate overall score
            total_indicators = sum(wash_indicators.values())
            max_possible = len(recent_txs) * 2

            score = (
                min(total_indicators / max_possible, 1.0) if max_possible > 0 else 0.0
            )

            return {
                "wash_trading_score": score,
                "evidence": wash_indicators,
                "transaction_count": len(recent_txs),
                "time_window_hours": time_window_hours,
                "analysis_time": current_time,
            }

        except Exception as e:
            logger.error(f"Error detecting wash trading patterns: {e}")
            return {"wash_trading_score": 0.0, "evidence": "analysis_error"}

    async def get_wallet_creation_time(self, wallet_address: str) -> Optional[datetime]:
        """Get when a wallet was first created by finding first transaction"""
        try:
            # This is expensive to do perfectly - we'll approximate by checking nonce
            nonce = self.web3.eth.get_transaction_count(wallet_address)

            if nonce == 0:
                # Brand new wallet or no outgoing transactions
                return None

            # For production, you'd want to use a more efficient method
            # This is a placeholder - in practice you'd use a block explorer API or indexed data
            # current_block = self.web3.eth.block_number
            # Using current_block calculation for future optimization
            # start_block = max(0, current_block - 1000000)  # Look back ~1 week

            # Binary search for first transaction would be more efficient
            return datetime.now() - timedelta(days=30)  # Placeholder

        except Exception as e:
            logger.error(f"Error getting wallet creation time: {e}")
            return None

    async def check_wallet_authenticity(self, wallet_address: str) -> Dict[str, Any]:
        """Comprehensive wallet authenticity check"""
        try:
            results = {
                "authentic": True,
                "risk_score": 0.0,
                "checks": {},
                "warnings": [],
            }

            # 1. Check transaction history depth
            tx_count = self.web3.eth.get_transaction_count(wallet_address)
            results["checks"]["tx_count"] = tx_count

            if tx_count < 10:
                results["warnings"].append("Low transaction count (<10)")
                results["risk_score"] += 0.2

            # 2. Check if wallet has received funds from known exchanges
            # (This would require additional data sources in production)
            results["checks"]["exchange_interactions"] = "not_implemented"

            # 3. Check for contract creation (EOA vs Contract)
            code = self.web3.eth.get_code(wallet_address)
            is_contract = len(code) > 0
            results["checks"]["is_contract"] = is_contract

            if is_contract:
                results["warnings"].append("Wallet is a smart contract")
                results["risk_score"] += 0.3

            # 4. Check recent activity patterns
            recent_txs = await self.get_wallet_transactions(wallet_address)
            results["checks"]["recent_tx_count"] = len(recent_txs)

            if len(recent_txs) == 0:
                results["warnings"].append("No recent transactions")
                results["risk_score"] += 0.1

            # 5. Check for suspicious patterns
            wash_results = await self.detect_wash_trading_patterns(wallet_address)
            results["checks"]["wash_trading"] = wash_results

            if wash_results.get("wash_trading_score", 0) > 0.5:
                results["warnings"].append("High wash trading score")
                results["risk_score"] += wash_results["wash_trading_score"]

            # Determine authenticity
            results["authentic"] = results["risk_score"] < 0.7
            results["risk_level"] = (
                "low"
                if results["risk_score"] < 0.3
                else "medium"
                if results["risk_score"] < 0.7
                else "high"
            )

            return results

        except Exception as e:
            logger.error(f"Error checking wallet authenticity: {e}")
            return {
                "authentic": False,
                "risk_score": 1.0,
                "error": str(e),
                "risk_level": "unknown",
            }

    async def health_check(self) -> bool:
        """Check if blockchain connection is healthy"""
        try:
            block_number = self.web3.eth.block_number
            if block_number > 0:
                logger.debug(
                    f"✅ Blockchain health check passed. Current block: {block_number}"
                )
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Blockchain health check failed: {e}")
            return False

    def close(self) -> None:
        """Close connections (if any)"""
        logger.info("CloseOperation: Blockchain API connection closed")
        # QuickNode connections are stateless, no explicit close needed
