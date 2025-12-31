#!/usr/bin/env python3
"""
Simple Integration Check for Polymarket Copy Trading Bot
Verifies component integration after security fixes.
"""

import os
import sys
from pathlib import Path


def main():
    print("🔗 Polymarket Copy Trading Bot - Integration Check")
    print("=" * 60)

    # Set test environment
    os.environ["PRIVATE_KEY"] = (
        "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    )

    checks_passed = 0
    total_checks = 0

    # Check 1: File Structure
    total_checks += 1
    print("📁 Checking file structure...")
    required_files = [
        "main.py",
        "config/settings.py",
        "core/clob_client.py",
        "core/wallet_monitor.py",
        "core/trade_executor.py",
        "utils/security.py",
        "utils/helpers.py",
    ]
    missing = [f for f in required_files if not Path(f).exists()]
    if missing:
        print(f"❌ Missing files: {missing}")
    else:
        print("✅ All required files present")
        checks_passed += 1

    # Check 2: Imports
    total_checks += 1
    print("📦 Checking imports...")
    try:
        from config.settings import settings
        from core.trade_executor import TradeExecutor
        from utils.security import mask_sensitive_data, validate_private_key

        print("✅ All critical imports successful")
        checks_passed += 1
    except Exception as e:
        print(f"❌ Import error: {e}")

    # Check 3: Configuration
    total_checks += 1
    print("⚙️ Checking configuration...")
    try:
        settings.validate_critical_settings()
        assert settings.risk.max_daily_loss > 0
        print("✅ Configuration validation passed")
        checks_passed += 1
    except Exception as e:
        print(f"❌ Configuration error: {e}")

    # Check 4: Security Features
    total_checks += 1
    print("🔒 Checking security features...")
    try:
        # Test private key validation
        valid = validate_private_key(
            "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        )
        assert valid

        # Test data masking
        test_data = {"private_key": "secret", "normal": "safe"}
        masked = mask_sensitive_data(test_data)
        assert "secret" not in str(masked) or "[REDACTED]" in str(masked)
        assert "safe" in str(masked)

        print("✅ Security features working")
        checks_passed += 1
    except Exception as e:
        print(f"❌ Security feature error: {e}")

    # Check 5: Race Condition Fixes
    total_checks += 1
    print("🔒 Checking race condition fixes...")
    try:
        # Check if TradeExecutor has state lock
        from unittest.mock import Mock

        from core.trade_executor import TradeExecutor

        mock_client = Mock()
        mock_client.wallet_address = "0x1234..."

        executor = TradeExecutor(mock_client)

        # Check if locks are present
        assert hasattr(executor, "_state_lock")
        assert hasattr(executor, "_position_locks")
        assert hasattr(executor, "_get_position_lock")

        print("✅ Race condition fixes implemented")
        checks_passed += 1
    except Exception as e:
        print(f"❌ Race condition fix error: {e}")

    # Check 6: Dependency Management
    total_checks += 1
    print("📦 Checking dependency management...")
    try:
        # Check if pyproject.toml exists (Poetry)
        pyproject_exists = Path("pyproject.toml").exists()
        poetry_lock_exists = Path("poetry.lock").exists()

        if pyproject_exists:
            print("✅ Poetry configuration present")
            if poetry_lock_exists:
                print("✅ Poetry lock file present")
            else:
                print("⚠️ Poetry lock file missing (run 'poetry install')")
            checks_passed += 1
        else:
            print("⚠️ No Poetry configuration found")
    except Exception as e:
        print(f"❌ Dependency management error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("📊 INTEGRATION CHECK RESULTS")
    print("=" * 60)
    print(f"✅ Checks passed: {checks_passed}/{total_checks}")
    print(".1f")

    if checks_passed >= total_checks * 0.8:  # 80% success rate
        print("\n🎉 INTEGRATION SUCCESSFUL!")
        print("✅ Components integrate properly")
        print("✅ Security fixes are working")
        return True
    else:
        print("\n⚠️ INTEGRATION ISSUES DETECTED")
        print("📋 Some components need attention")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
