"""Strategy Allocation Engine for Multi-Wallet Trade Distribution.

This module provides percentage-based trade allocation across multiple accounts,
enabling risk distribution and portfolio management.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from config.account_manager import AccountManager, WalletProfile
from utils.logging_security import SecureLogger

logger = logging.getLogger(__name__)


class AllocationResult:
    """Result of trade allocation across accounts."""

    def __init__(
        self,
        account_id: str,
        wallet_address: str,
        allocation_amount: Decimal,
        allocation_percentage: float,
        original_amount: Decimal,
    ) -> None:
        """
        Initialize allocation result.

        Args:
            account_id: Account ID receiving allocation
            wallet_address: Wallet address for this account
            allocation_amount: Amount allocated to this account
            allocation_percentage: Percentage of original trade allocated
            original_amount: Original trade amount
        """
        self.account_id = account_id
        self.wallet_address = wallet_address
        self.allocation_amount = allocation_amount
        self.allocation_percentage = allocation_percentage
        self.original_amount = original_amount

    def __repr__(self) -> str:
        return (
            f"AllocationResult(account={self.account_id[:10]}..., "
            f"amount=${self.allocation_amount:.2f}, {self.allocation_percentage:.1f}%)"
        )


class StrategyAllocator:
    """
    Allocates trades across multiple accounts based on percentage distribution.

    This class provides:
    - Percentage-based trade allocation
    - Balance-aware allocation (respects account balances)
    - Round-robin and weighted allocation strategies
    - Minimum trade amount enforcement
    - Allocation validation and error handling

    Thread Safety:
        Uses asyncio locks for concurrent operations
    """

    def __init__(self, account_manager: AccountManager) -> None:
        """
        Initialize strategy allocator.

        Args:
            account_manager: Account manager instance
        """
        self.account_manager = account_manager
        self._allocation_lock: asyncio.Lock = asyncio.Lock()

        # Allocation strategy tracking
        self.allocation_history: List[Dict[str, Any]] = []
        self.max_history_size: int = 1000

        SecureLogger.log(
            "info",
            "Initialized strategy allocator",
            {"account_count": len(self.account_manager.get_enabled_accounts())},
        )

    async def allocate_trade(
        self,
        original_trade: Dict[str, Any],
        trade_amount: Decimal,
        min_trade_amount: Optional[Decimal] = None,
    ) -> List[AllocationResult]:
        """
        Allocate a trade across multiple accounts based on allocation percentages.

        Args:
            original_trade: Original trade data
            trade_amount: Total trade amount to allocate
            min_trade_amount: Minimum trade amount per account (defaults to risk config)

        Returns:
            List of allocation results, one per account

        Raises:
            ValueError: If no enabled accounts or invalid allocation
        """
        async with self._allocation_lock:
            enabled_accounts = self.account_manager.get_enabled_accounts()

            if not enabled_accounts:
                # Fallback to single account mode (backward compatibility)
                logger.warning(
                    "No enabled accounts, falling back to single account mode"
                )
                return await self._allocate_single_account(original_trade, trade_amount)

            # Get minimum trade amount from first account's risk config
            if min_trade_amount is None:
                first_account = enabled_accounts[0]
                risk_config = self.account_manager.get_account_risk_config(
                    first_account.account_id
                )
                min_trade_amount = Decimal(str(risk_config.min_trade_amount))

            # Filter accounts that can handle the trade
            eligible_accounts = await self._filter_eligible_accounts(
                enabled_accounts, trade_amount, min_trade_amount
            )

            if not eligible_accounts:
                logger.warning(
                    f"⚠️ No eligible accounts for trade amount ${trade_amount:.2f} "
                    f"(min: ${min_trade_amount:.2f})"
                )
                return []

            # Allocate based on percentages
            allocations = await self._calculate_allocations(
                eligible_accounts, trade_amount, min_trade_amount
            )

            # Record allocation in history
            self._record_allocation(original_trade, allocations)

            logger.info(
                f"📊 Allocated ${trade_amount:.2f} across {len(allocations)} accounts: "
                f"{', '.join(f'{a.account_id[:8]}...({a.allocation_percentage:.1f}%)' for a in allocations)}"
            )

            return allocations

    async def _allocate_single_account(
        self, original_trade: Dict[str, Any], trade_amount: Decimal
    ) -> List[AllocationResult]:
        """Fallback allocation for single account mode (backward compatibility)."""
        # Try to get default account from settings
        try:
            from config.settings import settings

            wallet_address = settings.trading.wallet_address
            if not wallet_address:
                # Derive from private key
                from eth_account import Account

                account = Account.from_key(settings.trading.private_key)
                wallet_address = account.address

            account_id = wallet_address.lower()

            return [
                AllocationResult(
                    account_id=account_id,
                    wallet_address=wallet_address,
                    allocation_amount=trade_amount,
                    allocation_percentage=100.0,
                    original_amount=trade_amount,
                )
            ]

        except Exception as e:
            logger.error(f"Error in single account allocation: {e}", exc_info=True)
            return []

    async def _filter_eligible_accounts(
        self,
        accounts: List[WalletProfile],
        trade_amount: Decimal,
        min_trade_amount: Decimal,
    ) -> List[WalletProfile]:
        """
        Filter accounts that are eligible for trade allocation.

        Args:
            accounts: List of account profiles
            trade_amount: Total trade amount
            min_trade_amount: Minimum trade amount per account

        Returns:
            List of eligible accounts
        """
        eligible = []

        for account in accounts:
            # Check if account is enabled
            if not account.enabled:
                continue

            # Check allocation percentage
            if account.allocation_percentage <= 0:
                continue

            # Check account balance
            balance = await self.account_manager.get_balance(account.account_id)
            if balance is None:
                logger.warning(
                    f"⚠️ Could not get balance for {account.account_id[:10]}..."
                )
                continue

            # Calculate minimum allocation for this account
            min_allocation = trade_amount * Decimal(
                str(account.allocation_percentage / 100.0)
            )

            # Check if account has sufficient balance
            if balance < min_allocation:
                logger.debug(
                    f"⚠️ Account {account.account_id[:10]}... has insufficient balance: "
                    f"${balance:.2f} < ${min_allocation:.2f}"
                )
                continue

            # Check if allocation meets minimum trade amount
            if min_allocation < min_trade_amount:
                logger.debug(
                    f"⚠️ Account {account.account_id[:10]}... allocation ${min_allocation:.2f} "
                    f"below minimum ${min_trade_amount:.2f}"
                )
                continue

            eligible.append(account)

        return eligible

    async def _calculate_allocations(
        self,
        accounts: List[WalletProfile],
        trade_amount: Decimal,
        min_trade_amount: Decimal,
    ) -> List[AllocationResult]:
        """
        Calculate trade allocations across accounts.

        Args:
            accounts: Eligible accounts
            trade_amount: Total trade amount
            min_trade_amount: Minimum trade amount per account

        Returns:
            List of allocation results
        """
        allocations: List[AllocationResult] = []

        # Normalize allocation percentages (in case they don't sum to 100%)
        total_percentage = sum(account.allocation_percentage for account in accounts)
        if total_percentage == 0:
            # Equal distribution if no percentages set
            per_account_pct = 100.0 / len(accounts)
            for account in accounts:
                allocations.append(
                    AllocationResult(
                        account_id=account.account_id,
                        wallet_address=account.wallet_address,
                        allocation_amount=trade_amount
                        * Decimal(str(per_account_pct / 100.0)),
                        allocation_percentage=per_account_pct,
                        original_amount=trade_amount,
                    )
                )
            return allocations

        # Allocate based on percentages
        remaining_amount = trade_amount
        allocated_accounts = []

        for i, account in enumerate(accounts):
            # Calculate allocation percentage (normalized)
            normalized_pct = account.allocation_percentage / total_percentage

            # Calculate allocation amount
            if i == len(accounts) - 1:
                # Last account gets remaining amount to avoid rounding errors
                allocation_amount = remaining_amount
            else:
                allocation_amount = trade_amount * Decimal(str(normalized_pct))

            # Ensure minimum trade amount
            if allocation_amount < min_trade_amount:
                # Skip this account if allocation too small
                continue

            # Check balance
            balance = await self.account_manager.get_balance(account.account_id)
            if balance and balance < allocation_amount:
                # Reduce allocation to available balance
                allocation_amount = balance
                logger.warning(
                    f"⚠️ Reduced allocation for {account.account_id[:10]}... "
                    f"to available balance: ${allocation_amount:.2f}"
                )

            allocations.append(
                AllocationResult(
                    account_id=account.account_id,
                    wallet_address=account.wallet_address,
                    allocation_amount=allocation_amount,
                    allocation_percentage=normalized_pct * 100.0,
                    original_amount=trade_amount,
                )
            )

            remaining_amount -= allocation_amount
            allocated_accounts.append(account)

        # Ensure allocations sum to trade amount (adjust last allocation if needed)
        total_allocated = sum(a.allocation_amount for a in allocations)
        if allocations and abs(total_allocated - trade_amount) > Decimal("0.01"):
            # Adjust last allocation
            difference = trade_amount - total_allocated
            allocations[-1].allocation_amount += difference
            logger.debug(
                f"Adjusted last allocation by ${difference:.2f} to match total trade amount"
            )

        return allocations

    def _record_allocation(
        self, original_trade: Dict[str, Any], allocations: List[AllocationResult]
    ) -> None:
        """Record allocation in history."""
        allocation_record = {
            "timestamp": asyncio.get_event_loop().time(),
            "trade_id": original_trade.get("tx_hash", "unknown"),
            "original_amount": float(sum(a.original_amount for a in allocations)),
            "allocations": [
                {
                    "account_id": a.account_id,
                    "amount": float(a.allocation_amount),
                    "percentage": a.allocation_percentage,
                }
                for a in allocations
            ],
        }

        self.allocation_history.append(allocation_record)

        # Maintain history size
        if len(self.allocation_history) > self.max_history_size:
            self.allocation_history = self.allocation_history[-self.max_history_size :]

    async def get_allocation_stats(self) -> Dict[str, Any]:
        """
        Get statistics about trade allocations.

        Returns:
            Dictionary with allocation statistics
        """
        if not self.allocation_history:
            return {
                "total_allocations": 0,
                "total_trades_allocated": 0,
                "accounts_used": [],
            }

        # Calculate stats
        total_allocations = len(self.allocation_history)
        account_usage: Dict[str, int] = {}
        total_amount_allocated = Decimal("0.0")

        for record in self.allocation_history:
            total_amount_allocated += Decimal(str(record["original_amount"]))
            for allocation in record["allocations"]:
                account_id = allocation["account_id"]
                account_usage[account_id] = account_usage.get(account_id, 0) + 1

        return {
            "total_allocations": total_allocations,
            "total_trades_allocated": total_allocations,
            "total_amount_allocated": float(total_amount_allocated),
            "accounts_used": list(account_usage.keys()),
            "account_usage_counts": account_usage,
            "avg_allocation_per_trade": float(
                total_amount_allocated / total_allocations
            )
            if total_allocations > 0
            else 0.0,
        }

    async def validate_allocation(
        self, allocations: List[AllocationResult], original_amount: Decimal
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that allocations are correct.

        Args:
            allocations: List of allocation results
            original_amount: Original trade amount

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not allocations:
            return False, "No allocations provided"

        # Check that allocations sum to original amount (within tolerance)
        total_allocated = sum(a.allocation_amount for a in allocations)
        tolerance = Decimal("0.01")  # 1 cent tolerance

        if abs(total_allocated - original_amount) > tolerance:
            return (
                False,
                f"Allocations sum to ${total_allocated:.2f}, expected ${original_amount:.2f}",
            )

        # Check that all accounts exist and are enabled
        for allocation in allocations:
            account = self.account_manager.get_account(allocation.account_id)
            if not account:
                return False, f"Account {allocation.account_id} not found"

            if not account.enabled:
                return False, f"Account {allocation.account_id} is disabled"

        return True, None
