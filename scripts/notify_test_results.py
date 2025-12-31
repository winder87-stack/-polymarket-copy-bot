#!/usr/bin/env python3
"""
Script to send test results notifications via Telegram.

This script processes test results from GitHub Actions workflows
and sends formatted notifications to Telegram with success/failure status.

Usage:
    python scripts/notify_test_results.py \
        --workflow <workflow_name> \
        --run-id <run_id> \
        --status <status> \
        --branch <branch_name>
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from utils.alerts import send_telegram_alert
from utils.logger import get_logger

logger = get_logger(__name__)


class TestResultsNotifier:
    """Handle test result notifications."""

    def __init__(self, workflow: str, run_id: str, status: str, branch: str):
        """
        Initialize notifier.

        Args:
            workflow: GitHub workflow name
            run_id: GitHub Actions run ID
            status: Workflow status (success, failure, cancelled)
            branch: Git branch name
        """
        self.workflow = workflow
        self.run_id = run_id
        self.status = status
        self.branch = branch

    def load_test_results(self) -> Optional[Dict[str, Any]]:
        """
        Load test results from coverage reports.

        Returns:
            Test results dictionary or None if not available
        """
        # Look for coverage.json
        coverage_file = Path("coverage.json")
        if not coverage_file.exists():
            logger.warning("No coverage.json found")
            return None

        try:
            with open(coverage_file, "r") as f:
                data = json.load(f)
                totals = data.get("totals", {})
                return {
                    "total_lines": totals.get("num_statements", 0),
                    "covered_lines": totals.get("covered_lines", 0),
                    "missing_lines": totals.get("missing_lines", 0),
                    "coverage_percent": totals.get("percent_covered", 0.0) / 100.0,
                }
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading coverage.json: {e}")
            return None

    def format_message(self, test_results: Optional[Dict[str, Any]]) -> str:
        """
        Format test results message for Telegram.

        Args:
            test_results: Test results dictionary

        Returns:
            Formatted message string
        """
        # Build header
        status_emoji = {
            "success": "✅",
            "failure": "❌",
            "cancelled": "⚠️",
        }.get(self.status, "❓")

        status_text = {
            "success": "All Tests Passed",
            "failure": "Tests Failed",
            "cancelled": "Tests Cancelled",
        }.get(self.status, "Unknown")

        message = (
            f"{status_emoji} **{status_text}**\n"
            f"**Workflow:** {self.workflow}\n"
            f"**Run ID:** `{self.run_id}`\n"
            f"**Branch:** `{self.branch}`\n"
        )

        # Add coverage information if available
        if test_results:
            coverage = test_results["coverage_percent"]
            message += (
                f"**Coverage:** {coverage:.1%}\n"
                f"**Lines:** {test_results['covered_lines']}/{test_results['total_lines']}\n"
            )

            # Check if coverage is below target
            if coverage < 0.85:
                message += "⚠️ **Coverage below 85% target**\n"

        return message

    async def send_notification(self) -> None:
        """Send test results notification via Telegram."""
        # Load test results
        test_results = self.load_test_results()

        # Format message
        message = self.format_message(test_results)

        # Add timestamp
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        message += f"\n**Time:** {timestamp}"

        # Send notification
        try:
            await send_telegram_alert(message)
            logger.info(f"Test results notification sent: {self.status}")
        except Exception as e:
            logger.error(f"Error sending test results notification: {e}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Send test results notifications via Telegram"
    )

    parser.add_argument(
        "--workflow",
        type=str,
        required=True,
        help="GitHub workflow name",
    )

    parser.add_argument(
        "--run-id",
        type=str,
        required=True,
        help="GitHub Actions run ID",
    )

    parser.add_argument(
        "--status",
        type=str,
        required=True,
        choices=["success", "failure", "cancelled"],
        help="Workflow status",
    )

    parser.add_argument(
        "--branch",
        type=str,
        required=True,
        help="Git branch name",
    )

    return parser.parse_args()


async def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    args = parse_args()

    # Check for required environment variables
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not telegram_token or not telegram_chat_id:
        logger.error(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables are required"
        )
        return 1

    # Create notifier
    notifier = TestResultsNotifier(
        workflow=args.workflow,
        run_id=args.run_id,
        status=args.status,
        branch=args.branch,
    )

    # Send notification
    try:
        await notifier.send_notification()
        return 0
    except Exception as e:
        logger.error(f"Error sending notification: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
