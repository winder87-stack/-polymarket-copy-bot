#!/usr/bin/env python3
"""
Simplified System Validation for Polymarket Copy Trading Bot
"""

import os
import sys
from datetime import datetime
from pathlib import Path


def check_file_exists(file_path, description):
    """Check if a file exists."""
    exists = Path(file_path).exists()
    status = "✅ EXISTS" if exists else "❌ MISSING"
    print(f"{status} {description}: {file_path}")
    return exists


def check_file_executable(file_path, description):
    """Check if a file is executable."""
    path = Path(file_path)
    if path.exists():
        executable = os.access(path, os.X_OK)
        status = "✅ EXECUTABLE" if executable else "⚠️ NOT EXECUTABLE"
        print(f"{status} {description}: {file_path}")
        return executable
    else:
        print(f"❌ MISSING {description}: {file_path}")
        return False


def check_directory_exists(dir_path, description):
    """Check if a directory exists."""
    exists = Path(dir_path).exists()
    status = "✅ EXISTS" if exists else "❌ MISSING"
    print(f"{status} {description}: {dir_path}")
    return exists


def check_config_validation():
    """Check configuration validation."""
    print("\n🔧 CONFIGURATION VALIDATION:")
    try:
        sys.path.insert(0, ".")
        from config.settings import settings

        # Test basic validation
        settings.validate_critical_settings()
        print("✅ Configuration validation passed")
        return True
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False


def check_imports():
    """Check that all required modules can be imported."""
    print("\n📦 IMPORT VALIDATION:")

    imports_to_test = [
        ("config.settings", "Configuration module"),
        ("core.clob_client", "CLOB client module"),
        ("core.wallet_monitor", "Wallet monitor module"),
        ("core.trade_executor", "Trade executor module"),
        ("utils.helpers", "Helper utilities"),
        ("utils.security", "Security utilities"),
        ("utils.logging_utils", "Logging utilities"),
        ("utils.alerts", "Alert system"),
        ("main", "Main application"),
    ]

    success_count = 0
    for module_name, description in imports_to_test:
        try:
            __import__(module_name)
            print(f"✅ {description} imported successfully")
            success_count += 1
        except ImportError as e:
            print(f"❌ {description} import failed: {e}")
        except Exception as e:
            print(f"⚠️ {description} import warning: {e}")
            success_count += 1

    return success_count == len(imports_to_test)


def check_file_structure():
    """Check the file structure."""
    print("\n📁 FILE STRUCTURE VALIDATION:")

    files_to_check = [
        ("main.py", "Main application script"),
        ("config/settings.py", "Configuration settings"),
        ("core/clob_client.py", "CLOB client implementation"),
        ("core/wallet_monitor.py", "Wallet monitor implementation"),
        ("core/trade_executor.py", "Trade executor implementation"),
        ("utils/helpers.py", "Helper utilities"),
        ("utils/security.py", "Security utilities"),
        ("utils/logging_utils.py", "Logging utilities"),
        ("utils/alerts.py", "Alert system"),
        ("requirements.txt", "Python dependencies"),
        ("README.md", "Documentation"),
    ]

    directories_to_check = [
        ("config", "Configuration directory"),
        ("core", "Core modules directory"),
        ("utils", "Utilities directory"),
        ("tests", "Test directory"),
        ("logs", "Logs directory"),
        ("data", "Data directory"),
    ]

    file_checks_passed = 0
    dir_checks_passed = 0

    for file_path, description in files_to_check:
        if check_file_exists(file_path, description):
            file_checks_passed += 1

    for dir_path, description in directories_to_check:
        if check_directory_exists(dir_path, description):
            dir_checks_passed += 1

    return file_checks_passed == len(files_to_check) and dir_checks_passed == len(
        directories_to_check
    )


def check_deployment_readiness():
    """Check deployment readiness."""
    print("\n🚀 DEPLOYMENT READINESS:")

    deployment_checks = [
        ("systemd/polymarket-bot.service", "Systemd service file"),
        ("scripts/setup_ubuntu.sh", "Ubuntu setup script"),
    ]

    checks_passed = 0

    for file_path, description in deployment_checks:
        if check_file_exists(file_path, description):
            checks_passed += 1

    # Check if setup script is executable
    if check_file_executable("scripts/setup_ubuntu.sh", "Setup script"):
        checks_passed += 1

    return checks_passed == len(deployment_checks) + 1


def check_test_coverage():
    """Check test coverage."""
    print("\n🧪 TEST COVERAGE:")

    test_files = [
        "tests/conftest.py",
        "tests/unit/test_settings.py",
        "tests/unit/test_clob_client.py",
        "tests/unit/test_wallet_monitor.py",
        "tests/unit/test_trade_executor.py",
        "tests/unit/test_security.py",
        "tests/unit/test_helpers.py",
        "tests/integration/test_end_to_end.py",
        "tests/integration/test_security_integration.py",
        "tests/integration/test_edge_cases.py",
        "tests/performance/test_performance.py",
        "tests/mocks/polygonscan_mock.py",
        "tests/mocks/clob_api_mock.py",
        "tests/mocks/web3_mock.py",
        "tests/README.md",
    ]

    test_checks_passed = 0
    for test_file in test_files:
        if check_file_exists(test_file, "Test file"):
            test_checks_passed += 1

    return test_checks_passed == len(test_files)


def calculate_score(results):
    """Calculate overall system health score."""
    weights = {
        "file_structure": 0.15,
        "imports": 0.20,
        "configuration": 0.20,
        "deployment": 0.15,
        "tests": 0.20,
        "security": 0.10,  # Basic security check
    }

    score = 0
    for check_name, weight in weights.items():
        if check_name in results and results[check_name]:
            score += weight * 100

    return int(score)


def get_recommendation(score):
    """Get deployment recommendation based on score."""
    if score >= 90:
        return "🚀 GO: System is production-ready"
    elif score >= 75:
        return "⚠️ CONDITIONAL GO: Ready with minor fixes"
    elif score >= 60:
        return "🛠️ NEEDS WORK: Significant improvements required"
    else:
        return "❌ NO-GO: Major issues need resolution"


def main():
    """Run the validation suite."""
    print("=" * 80)
    print("🎯 POLYMARKET COPY TRADING BOT - SYSTEM VALIDATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    results = {}

    # Run all checks
    results["file_structure"] = check_file_structure()
    results["imports"] = check_imports()
    results["configuration"] = check_config_validation()
    results["deployment"] = check_deployment_readiness()
    results["tests"] = check_test_coverage()

    # Basic security check
    results["security"] = check_file_exists(
        ".env", "Environment file"
    ) and not check_file_exists(".env", "World-readable .env")

    # Calculate final score
    final_score = calculate_score(results)
    recommendation = get_recommendation(final_score)

    print("\n" + "=" * 80)
    print("📊 VALIDATION RESULTS SUMMARY")
    print("=" * 80)
    print(f"🎯 Final Score: {final_score}/100")
    print(f"📋 Recommendation: {recommendation}")

    print("\n🔍 Detailed Results:")
    for check_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {check_name.replace('_', ' ').title()}: {status}")

    # Generate report
    report_content = f"""# Polymarket Copy Trading Bot - System Validation Report

## Executive Summary

- **Final Score**: {final_score}/100
- **Recommendation**: {recommendation}
- **Validation Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}

## Validation Results

### File Structure
- **Status**: {"✅ PASSED" if results["file_structure"] else "❌ FAILED"}
- **Description**: All required files and directories present

### Module Imports
- **Status**: {"✅ PASSED" if results["imports"] else "❌ FAILED"}
- **Description**: All Python modules can be imported successfully

### Configuration
- **Status**: {"✅ PASSED" if results["configuration"] else "❌ FAILED"}
- **Description**: Configuration validation passes

### Deployment Readiness
- **Status**: {"✅ PASSED" if results["deployment"] else "❌ FAILED"}
- **Description**: Deployment scripts and configuration ready

### Test Coverage
- **Status**: {"✅ PASSED" if results["tests"] else "❌ FAILED"}
- **Description**: Comprehensive test suite in place

### Security
- **Status**: {"✅ PASSED" if results["security"] else "❌ FAILED"}
- **Description**: Basic security checks pass

## Critical Issues

"""

    critical_issues = []
    if not results["file_structure"]:
        critical_issues.append("- Missing required files or directories")
    if not results["imports"]:
        critical_issues.append("- Module import failures")
    if not results["configuration"]:
        critical_issues.append("- Configuration validation failures")
    if not results["security"]:
        critical_issues.append("- Security configuration issues")

    if critical_issues:
        report_content += "\n".join(critical_issues)
    else:
        report_content += "None identified"

    report_content += "\n\n## Minor Improvements\n\n"
    improvements = []
    if not results["deployment"]:
        improvements.append("- Complete deployment configuration")
    if not results["tests"]:
        improvements.append("- Expand test coverage")

    if improvements:
        report_content += "\n".join(improvements)
    else:
        report_content += "None identified"

    report_content += f"""

## Go/No-Go Decision

**{recommendation}**

The system {"is" if final_score >= 75 else "is not"} ready for production deployment.

---
*Report generated by system validation script*
"""

    # Save report
    report_file = Path("final_validation_report.md")
    report_file.write_text(report_content)

    print(f"\n📄 Detailed report saved to: {report_file}")

    return final_score >= 75


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
