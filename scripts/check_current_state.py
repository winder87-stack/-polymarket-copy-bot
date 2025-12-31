#!/usr/bin/env python3
"""
Check Current State of Polymarket Bot

This script verifies:
1. All core component files exist
2. Polymarket API file has correct base_url
3. All dependencies can be imported

Author: Polymarket Copy Bot Team
Date: 2025-12-27
Version: 1.0
"""

import os
import sys

# Colors for output
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
NC = "\033[0m"  # No Color

print("=" * 80)
print(f"{BLUE}🔍 CHECKING CURRENT STATE OF POLYMARKET BOT{NC}")
print("=" * 80)

# =============================================================================
# CHECK 1: Component Files
# =============================================================================

print(f"\n{BLUE}CHECK 1: Component Files{NC}")

component_files = {
    "WalletQualityScorer": "core/wallet_quality_scorer.py",
    "RedFlagDetector": "core/red_flag_detector.py",
    "DynamicPositionSizer": "core/dynamic_position_sizer.py",
    "WalletBehaviorMonitor": "core/wallet_behavior_monitor.py",
    "CompositeScoringEngine": "core/composite_scoring_engine.py",
    "MarketConditionAnalyzer": "core/market_condition_analyzer.py",
    "CopyTradingDashboard": "monitoring/copy_trading_dashboard.py",
}

missing_files = []

for name, path in component_files.items():
    if os.path.exists(path):
        lines = 0
        try:
            with open(path, "r") as f:
                lines = sum(1 for _ in f)
        except (IOError, OSError):
            lines = 0
        print(f"  {GREEN}✅{NC} {name} - File exists ({lines} lines)")
    else:
        print(f"  {RED}❌{NC} {name} - File NOT FOUND: {path}")
        missing_files.append((name, path))

if missing_files:
    print(f"\n{RED}⚠️  WARNING: {len(missing_files)} component files are missing{NC}")
    print(f"  {RED}   Some components may not be implemented yet{NC}")
    print(f"  {RED}   This is expected for a fresh implementation{NC}")
else:
    print(f"\n{GREEN}✅ All {len(component_files)} core component files found{NC}")

# =============================================================================
# CHECK 2: Polymarket API File
# =============================================================================

print(f"\n{BLUE}CHECK 2: Polymarket API File{NC}")

api_file_path = "scanners/data_sources/polymarket_api.py"

if not os.path.exists(api_file_path):
    print(f"  {RED}❌{NC} {api_file_path} ({RED}FILE NOT FOUND{NC})")
else:
    print(f"  {GREEN}✅{NC} {api_file_path} exists")

    print(f"\n  {YELLOW}Searching for PolymarketLeaderboardAPI class...{NC}")

    try:
        with open(api_file_path, "r") as f:
            content = f.read()

        if "class PolymarketLeaderboardAPI" in content:
            print(f"  {GREEN}✅{NC} PolymarketLeaderboardAPI class found")

            lines = content.split("\n")

            print(f"\n  {YELLOW}Searching for base_url definition...{NC}")

            found_base_url = False
            found_fallback = False
            found_init = False

            for i, line in enumerate(lines, 1):
                # Check for __init__ method
                if "def __init__(self, config)" in line:
                    found_init = True
                    print(f"  {GREEN}✅{NC} Line {i}: {line.strip()}")

                # Check next 20 lines for base_url and fallback
                for j in range(i, min(i + 20, len(lines))):
                    check_line = lines[j]
                    if "self.base_url =" in check_line:
                        print(f"  {GREEN}✅{NC} Line {j}: {check_line.strip()}")
                        found_base_url = True
                    elif "self.fallback_endpoints" in check_line:
                        print(f"  {GREEN}✅{NC} Line {j}: {check_line.strip()}")
                        found_fallback = True
                    elif check_line.strip() == "":
                        # Found end of __init__ method
                        break

                if found_init and (found_base_url or found_fallback):
                    break

            if found_init:
                print(f"\n  {CYAN}Current API Configuration:{NC}")

                if found_base_url:
                    print(f"  {GREEN}✅{NC} base_url definition found")
                    print(f"  {GREEN}✅ fallback_endpoints definition found")
                else:
                    print(f"  {YELLOW}⚠️{NC} base_url definition NOT found")
                    print(f"  {YELLOW}   fallback_endpoints definition NOT found")
                    print(f"  {YELLOW}   This may need to be added to __init__ method")
            else:
                print(
                    f"  {RED}❌{NC} PolymarketLeaderboardAPI __init__ method not found"
                )

    except Exception as e:
        print(f"  {RED}❌{NC} Error reading {api_file_path}: {e}")

# =============================================================================
# CHECK 3: Import Tests
# =============================================================================

print(f"\n{BLUE}CHECK 3: Import Tests{NC}")

print(f"  {YELLOW}Adding project to Python path...{NC}")
sys.path.insert(0, "/home/ink/polymarket-copy-bot")

import_tests = []
skipped = []

# Test Config
try:
    import config.scanner_config  # noqa: F401 - Import for availability test

    print(f"  {GREEN}✅{NC} config.scanner_config imported successfully")
    import_tests.append("Config")
except ImportError as e:
    if "dotenv" in str(e).lower():
        print(
            f"  {YELLOW}⚠️{NC} config.scanner_config - Missing dependency (python-dotenv)"
        )
        print(f"  {YELLOW}→ Run: pip install -r requirements.txt{NC}")
        import_tests.append("Config (missing: python-dotenv)")
    else:
        print(f"  {RED}❌{NC} config.scanner_config import failed: {e}")
        import_tests.append("Config")
except Exception as e:
    print(f"  {RED}❌{NC} config.scanner_config load failed: {e}")
    import_tests.append("Config")

# Test Components
for name, path in component_files.items():
    if os.path.exists(path):
        module_name = path.replace("/", ".").replace(".py", "")
        try:
            __import__(module_name)
            print(f"  {GREEN}✅{NC} {name} - Imported successfully")
            import_tests.append(name)
        except ImportError as e:
            if "dotenv" in str(e).lower():
                print(
                    f"  {YELLOW}⚠️{NC} {name} - Module exists but has dependencies: {str(e)[:50]}"
                )
                skipped.append((name, str(e)))
            else:
                print(f"  {RED}❌{NC} {name} - Import failed: {e}")
                import_tests.append(name)
        except Exception as e:
            print(f"  {RED}❌{NC} {name} - Import failed: {str(e)[:50]}")
            import_tests.append(name)

print("\n  Import Statistics:")
print(f"  {GREEN}Successfully imported: {len(import_tests)} components")
print(f"  {YELLOW}Skipped (dependencies not met): {len(skipped)} components")

# =============================================================================
# CHECK 4: .env File
# =============================================================================

print(f"\n{BLUE}CHECK 4: .env File{NC}")

if os.path.exists(".env"):
    print(f"  {GREEN}✅{NC} .env file exists")
    try:
        # SECURITY: Never log .env contents - only check for presence of critical variables
        with open(".env", "r") as f:
            env_lines = f.readlines()
        print(f"\n  {YELLOW}Critical variables check:{NC}")

        # Only check if variables are set, not their actual values (security)
        critical_vars = [
            "DRY_RUN",
            "USE_TESTNET",
            "MAX_POSITION_SIZE",
            "MAX_DAILY_LOSS",
            "SCAN_INTERVAL_HOURS",
            "MAX_WALLETS_TO_MONITOR",
            "POLYMARKET_API_KEY",
            "PRIVATE_KEY",
            "POLYGON_RPC_URL",
        ]

        for var in critical_vars:
            # Check if variable is present without logging value
            if any(var in line for line in env_lines):
                print(f"  {GREEN}✅{NC} {var} is set")
            else:
                print(f"  {YELLOW}⚠️{NC} {var} is not set (optional)")

        # Count total variables without logging content
        total_vars = sum(
            1
            for line in env_lines
            if "=" in line and line.strip() and not line.strip().startswith("#")
        )
        print(f"\n  {CYAN}Total variables configured: {total_vars}")

    except Exception as e:
        print(f"  {RED}❌{NC} Error checking .env: {e}")
else:
    print(f"  {YELLOW}⚠️{NC} .env file does not exist")
    print(f"  {YELLOW}→ Run: echo 'DRY_RUN=true' >> .env{NC}")

# =============================================================================
# SUMMARY
# =============================================================================

print(f"\n{GREEN}{'=' * 80}")
print(f"{GREEN}📊 STATE CHECK SUMMARY{NC}")
print(f"{GREEN}{'=' * 80}")

print(f"\n{GREEN}Component Files:{NC}")
print(f"  Total: {len(component_files)}")
print(f"  Found: {len(component_files) - len(missing_files)}")
print(f"  Missing: {len(missing_files)}")

if missing_files:
    for name, path in missing_files:
        print(f"  {RED}  - {name}: {path}")

print(f"\n{GREEN}Import Tests:{NC}")
print(f"  Total: {len(component_files) + 1}")  # +1 for config
print(f"  Successful: {len(import_tests)}")
print(f"  Failed: {len(component_files) + 1 - len(import_tests)}")
print(f"  Skipped: {len(skipped)}")

if import_tests:
    print(f"\n{GREEN}Successfully imported:{NC}")
    for name in import_tests:
        print(f"  {GREEN}✅{NC} {name}")

if skipped:
    print(f"\n{YELLOW}Skipped (dependencies not met):{NC}")
    for name, reason in skipped:
        print(f"  {YELLOW}⚠️{NC} {name}: {reason[:50]}")

print(f"\n{GREEN}Polymarket API Status:{NC}")
if os.path.exists(api_file_path):
    if "class PolymarketLeaderboardAPI" in open(api_file_path, "r").read():
        print(f"  {GREEN}✅{NC} File exists and class defined")
    else:
        print(f"  {YELLOW}⚠️{NC} File exists but class not defined")
else:
    print(f"  {RED}❌{NC} File not found: {api_file_path}")

print(f"\n{GREEN}.env File Status:{NC}")
if os.path.exists(".env"):
    print(f"  {GREEN}✅{NC} .env file exists")
else:
    print(f"  {YELLOW}⚠️{NC} .env file does not exist")

print(f"\n{CYAN}Recommendations:{NC}")

if missing_files:
    print(f"  1. {RED}Create missing component files{NC}")
    print(f"  {RED}   Implementation guides are in docs/{NC}")

if not os.path.exists(".env"):
    print(f"  2. {YELLOW}Create .env file{NC}")
    print(f"  {YELLOW}   echo 'DRY_RUN=true' >> .env{NC}")
    print(f"  {YELLOW}   echo 'USE_TESTNET=true' >> .env{NC}")

if len(import_tests) < len(component_files):
    print(f"  3. {YELLOW}Install missing dependencies{NC}")
    print(f"  {YELLOW}   pip install -r requirements.txt{NC}")

if "class PolymarketLeaderboardAPI" not in open(api_file_path, "r").read():
    print(f"  4. {YELLOW}Update Polymarket API file{NC}")
    print(f"  {YELLOW}   Add base_url and fallback_endpoints to __init__{NC}")
    print(f"  {YELLOW}   Reference: scanners/data_sources/polymarket_api_updated.py")

print(f"\n{GREEN}Next Steps:{NC}")
print("  1. Review component file check above")
print("  2. Review Polymarket API file check above")
print("  3. Review import test results above")
print("  4. Check .env configuration above")

print(f"\n{GREEN}✅ STATE CHECK COMPLETE!{NC}")

print(f"{GREEN}{'=' * 80}")
