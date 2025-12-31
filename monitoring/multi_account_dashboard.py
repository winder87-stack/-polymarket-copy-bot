"""Unified Reporting Dashboard for Multi-Account Operations.

This module provides comprehensive reporting and monitoring for multiple trading accounts,
aggregating metrics, performance, and risk data across all accounts.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from config.account_manager import AccountManager
from core.strategy_allocator import StrategyAllocator
from utils.logging_security import SecureLogger

logger = logging.getLogger(__name__)


class MultiAccountDashboard:
    """
    Unified reporting dashboard for multi-account operations.

    This class provides:
    - Aggregated performance metrics across all accounts
    - Per-account performance breakdown
    - Risk metrics and alerts
    - Allocation statistics
    - Historical performance tracking

    Thread Safety:
        Uses asyncio locks for concurrent operations
    """

    def __init__(
        self,
        account_manager: AccountManager,
        strategy_allocator: Optional[StrategyAllocator] = None,
    ) -> None:
        """
        Initialize multi-account dashboard.

        Args:
            account_manager: Account manager instance
            strategy_allocator: Optional strategy allocator for allocation stats
        """
        self.account_manager = account_manager
        self.strategy_allocator = strategy_allocator
        self._report_lock: asyncio.Lock = asyncio.Lock()

        # Performance tracking
        self.performance_history: List[Dict[str, Any]] = []
        self.max_history_size: int = 1000

        SecureLogger.log("info", "Initialized multi-account dashboard")

    async def get_unified_report(self) -> Dict[str, Any]:
        """
        Get comprehensive unified report across all accounts.

        Returns:
            Dictionary with aggregated metrics and per-account breakdown
        """
        async with self._report_lock:
            enabled_accounts = self.account_manager.get_enabled_accounts()

            # Get account metrics
            account_metrics = self.account_manager.get_unified_metrics()

            # Get allocation stats if available
            allocation_stats = {}
            if self.strategy_allocator:
                allocation_stats = await self.strategy_allocator.get_allocation_stats()

            # Calculate aggregated metrics
            aggregated = await self._calculate_aggregated_metrics(enabled_accounts)

            # Get risk summary
            risk_summary = await self._calculate_risk_summary(enabled_accounts)

            # Get performance trends
            performance_trends = await self._calculate_performance_trends()

            report = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "total_accounts": len(enabled_accounts),
                    "enabled_accounts": len(enabled_accounts),
                    "total_balance_usdc": float(account_metrics["total_balance_usdc"]),
                    **aggregated,
                },
                "accounts": account_metrics["accounts"],
                "allocation": allocation_stats,
                "risk": risk_summary,
                "performance": performance_trends,
            }

            # Store in history
            self._store_report_in_history(report)

            return report

    async def _calculate_aggregated_metrics(
        self, accounts: List[Any]
    ) -> Dict[str, Any]:
        """Calculate aggregated metrics across all accounts."""
        total_balance = Decimal("0.0")
        total_trades = 0
        total_pnl = Decimal("0.0")
        daily_pnl = Decimal("0.0")
        total_allocation = 0.0

        for account in accounts:
            balance = await self.account_manager.get_balance(account.account_id)
            if balance:
                total_balance += balance

            account_balance = self.account_manager.account_balances.get(
                account.account_id
            )
            if account_balance:
                total_trades += account_balance.total_trades
                total_pnl += account_balance.total_pnl
                daily_pnl += account_balance.daily_pnl

            total_allocation += account.allocation_percentage

        return {
            "total_balance_usdc": float(total_balance),
            "total_trades": total_trades,
            "total_pnl_usdc": float(total_pnl),
            "daily_pnl_usdc": float(daily_pnl),
            "total_allocation_percentage": total_allocation,
            "avg_balance_per_account": float(total_balance / len(accounts))
            if accounts
            else 0.0,
        }

    async def _calculate_risk_summary(self, accounts: List[Any]) -> Dict[str, Any]:
        """Calculate risk summary across all accounts."""
        risk_configs = []
        circuit_breaker_active_count = 0
        low_balance_count = 0

        for account in accounts:
            risk_config = self.account_manager.get_account_risk_config(
                account.account_id
            )
            risk_configs.append(risk_config)

            balance = await self.account_manager.get_balance(account.account_id)
            if balance and balance < Decimal(str(account.min_balance_usdc)):
                low_balance_count += 1

        # Aggregate risk parameters
        max_position_sizes = [rc.max_position_size for rc in risk_configs]
        max_daily_losses = [rc.max_daily_loss for rc in risk_configs]

        return {
            "total_max_position_size": sum(max_position_sizes),
            "avg_max_position_size": sum(max_position_sizes) / len(max_position_sizes)
            if max_position_sizes
            else 0.0,
            "total_max_daily_loss": sum(max_daily_losses),
            "avg_max_daily_loss": sum(max_daily_losses) / len(max_daily_losses)
            if max_daily_losses
            else 0.0,
            "circuit_breaker_active_accounts": circuit_breaker_active_count,
            "low_balance_accounts": low_balance_count,
            "risk_configs_count": len(risk_configs),
        }

    async def _calculate_performance_trends(self) -> Dict[str, Any]:
        """Calculate performance trends from history."""
        if not self.performance_history:
            return {
                "trend": "insufficient_data",
                "periods_analyzed": 0,
            }

        # Analyze last 24 hours if available
        recent_reports = [
            r
            for r in self.performance_history
            if datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            > datetime.now(timezone.utc) - timedelta(hours=24)
        ]

        if len(recent_reports) < 2:
            return {
                "trend": "insufficient_data",
                "periods_analyzed": len(recent_reports),
            }

        # Calculate trend
        first_balance = recent_reports[0]["summary"]["total_balance_usdc"]
        last_balance = recent_reports[-1]["summary"]["total_balance_usdc"]

        balance_change = last_balance - first_balance
        balance_change_pct = (
            (balance_change / first_balance * 100) if first_balance > 0 else 0.0
        )

        return {
            "trend": "increasing"
            if balance_change > 0
            else "decreasing"
            if balance_change < 0
            else "stable",
            "balance_change_24h": balance_change,
            "balance_change_pct_24h": balance_change_pct,
            "periods_analyzed": len(recent_reports),
            "first_balance": first_balance,
            "last_balance": last_balance,
        }

    def _store_report_in_history(self, report: Dict[str, Any]) -> None:
        """Store report in history for trend analysis."""
        self.performance_history.append(report)

        # Maintain history size
        if len(self.performance_history) > self.max_history_size:
            self.performance_history = self.performance_history[
                -self.max_history_size :
            ]

    async def get_account_performance_report(
        self, account_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed performance report for a specific account.

        Args:
            account_id: Account ID

        Returns:
            Performance report or None if account not found
        """
        account = self.account_manager.get_account(account_id)
        if not account:
            return None

        balance = await self.account_manager.get_balance(account_id)
        account_balance = self.account_manager.account_balances.get(account_id)

        if not account_balance:
            return None

        risk_config = self.account_manager.get_account_risk_config(account_id)

        return {
            "account_id": account_id,
            "wallet_address": account.wallet_address,
            "enabled": account.enabled,
            "allocation_percentage": account.allocation_percentage,
            "balance_usdc": float(balance) if balance else 0.0,
            "total_trades": account_balance.total_trades,
            "total_pnl_usdc": float(account_balance.total_pnl),
            "daily_pnl_usdc": float(account_balance.daily_pnl),
            "risk_config": {
                "max_position_size": risk_config.max_position_size,
                "max_daily_loss": risk_config.max_daily_loss,
                "min_trade_amount": risk_config.min_trade_amount,
                "max_concurrent_positions": risk_config.max_concurrent_positions,
            },
            "tags": account.tags,
            "last_updated": account_balance.last_updated.isoformat(),
        }

    async def get_risk_alerts(self) -> List[Dict[str, Any]]:
        """
        Get risk alerts for all accounts.

        Returns:
            List of risk alerts
        """
        alerts = []
        enabled_accounts = self.account_manager.get_enabled_accounts()

        for account in enabled_accounts:
            balance = await self.account_manager.get_balance(account.account_id)
            if balance and balance < Decimal(str(account.min_balance_usdc)):
                alerts.append(
                    {
                        "type": "low_balance",
                        "account_id": account.account_id,
                        "severity": "warning",
                        "message": f"Account {account.account_id[:10]}... balance ${balance:.2f} "
                        f"below minimum ${account.min_balance_usdc:.2f}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

            # Check max balance if set
            if account.max_balance_usdc and balance:
                if balance > Decimal(str(account.max_balance_usdc)):
                    alerts.append(
                        {
                            "type": "high_balance",
                            "account_id": account.account_id,
                            "severity": "info",
                            "message": f"Account {account.account_id[:10]}... balance ${balance:.2f} "
                            f"above maximum ${account.max_balance_usdc:.2f}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

        return alerts

    async def format_report_for_display(
        self, report: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format unified report as human-readable string.

        Args:
            report: Optional report to format (fetches if not provided)

        Returns:
            Formatted report string
        """
        if report is None:
            report = await self.get_unified_report()

        lines = []
        lines.append("=" * 80)
        lines.append("MULTI-ACCOUNT TRADING DASHBOARD")
        lines.append("=" * 80)
        lines.append(f"Report Time: {report['timestamp']}")
        lines.append("")

        # Summary
        summary = report["summary"]
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Accounts: {summary['total_accounts']}")
        lines.append(f"Total Balance: ${summary['total_balance_usdc']:,.2f}")
        lines.append(f"Total Trades: {summary['total_trades']}")
        lines.append(f"Total P&L: ${summary['total_pnl_usdc']:,.2f}")
        lines.append(f"Daily P&L: ${summary['daily_pnl_usdc']:,.2f}")
        lines.append("")

        # Per-account breakdown
        lines.append("ACCOUNT BREAKDOWN")
        lines.append("-" * 80)
        for account in report["accounts"]:
            lines.append(f"Account: {account['account_id'][:20]}...")
            lines.append(f"  Balance: ${account['balance_usdc']:,.2f}")
            lines.append(f"  Allocation: {account['allocation_percentage']:.1f}%")
            lines.append(f"  Trades: {account['total_trades']}")
            lines.append(f"  P&L: ${account['total_pnl']:,.2f}")
            lines.append(f"  Daily P&L: ${account['daily_pnl']:,.2f}")
            lines.append("")

        # Risk summary
        risk = report["risk"]
        lines.append("RISK SUMMARY")
        lines.append("-" * 80)
        lines.append(
            f"Total Max Position Size: ${risk['total_max_position_size']:,.2f}"
        )
        lines.append(f"Total Max Daily Loss: ${risk['total_max_daily_loss']:,.2f}")
        lines.append(f"Low Balance Accounts: {risk['low_balance_accounts']}")
        lines.append("")

        # Performance trends
        perf = report["performance"]
        if perf.get("trend") != "insufficient_data":
            lines.append("PERFORMANCE TRENDS (24h)")
            lines.append("-" * 80)
            lines.append(f"Trend: {perf['trend'].upper()}")
            lines.append(f"Balance Change: ${perf.get('balance_change_24h', 0):,.2f}")
            lines.append(
                f"Balance Change %: {perf.get('balance_change_pct_24h', 0):.2f}%"
            )
            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)
