#!/bin/bash
###############################################################################
# Set Up Test Environment (Critical)
###############################################################################
# Activates venv and sets up test environment for scanner benchmarks
###############################################################################

set -e  # Exit on error

echo "================================================================================"
echo "🚀 SETTING UP TEST ENVIRONMENT"
echo "================================================================================"

# 1. Activate venv
echo "📋 1. Activating venv..."
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ venv not found at venv/bin/activate"
    echo "   Please run: python3 -m venv venv"
    exit 1
fi

source venv/bin/activate

# 2. Set test environment variables
echo "📋 2. Setting test environment variables..."
export TEST_ENV=true
export USE_TESTNET=true
export DRY_RUN=true
export MAX_DAILY_LOSS=10.00
export MAX_POSITION_SIZE=1.00
export SCAN_INTERVAL_SECONDS=10
export LOG_LEVEL=DEBUG

echo "   ✅ TEST_ENV=true"
echo "   ✅ USE_TESTNET=true"
echo "   ✅ DRY_RUN=true"
echo "   ✅ MAX_DAILY_LOSS=10.00"
echo "   ✅ MAX_POSITION_SIZE=1.00"
echo "   ✅ SCAN_INTERVAL_SECONDS=10"
echo "   ✅ LOG_LEVEL=DEBUG"

# 3. Verify Python version
echo "📋 3. Verifying Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "   ✅ Python: $PYTHON_VERSION"

# 4. Verify critical modules
echo "📋 4. Verifying critical modules..."

python3 << 'EOF'
modules_to_check = [
    "asyncio",
    "aiohttp",
    "pydantic",
    "psutil",
]

for module in modules_to_check:
    try:
        __import__(module)
        print(f"   ✅ {module}")
    except ImportError:
        print(f"   ❌ {module} NOT FOUND")

# Verify project modules
project_modules = [
    ("scanners.high_performance_wallet_scanner", "HighPerformanceWalletScanner"),
    ("config.scanner_config", "ScannerConfig"),
    ("core.circuit_breaker", "CircuitBreaker"),
    ("utils.helpers", "BoundedCache"),
    ("utils.bounded_cache", "BoundedCache"),
    ("utils.performance_monitor", "PerformanceMonitor"),
]

for module_path, class_name in project_modules:
    try:
        parts = module_path.split(".")
        module_name = parts[-1]
        __import__(module_path)
        if class_name in dir():
            print(f"   ✅ {module_path}.{class_name}")
        else:
            print(f"   ⚠️  {module_path} imported but {class_name} not found")
    except ImportError as e:
        print(f"   ❌ {module_path}: {e}")

EOF

# 5. Create test data directory if needed
echo "📋 5. Setting up test data directories..."
mkdir -p tests/integration/test_data
mkdir -p benchmarks/simulation
mkdir -p data/wallet_samples

echo "   ✅ Created test data directories"

# 6. Run validation
echo "📋 6. Running validation..."
python3 << 'EOF'
import sys
sys.path.insert(0, ".")

# Test imports
try:
    from utils.bounded_cache import BoundedCache
    cache = BoundedCache(max_size=100, ttl_seconds=60)
    print("   ✅ BoundedCache import successful")
    print(f"   ✅ BoundedCache created: max_size={cache.max_size}, ttl={cache.ttl_seconds}s")

    from utils.performance_monitor import PERFORMANCE_MONITOR
    monitor = PERFORMANCE_MONITOR(window_size=100)
    print("   ✅ PerformanceMonitor import successful")
    print(f"   ✅ PerformanceMonitor created: window_size={monitor.window_size}")

    from config.scanner_config import ScannerConfig, RiskFrameworkConfig
    print("   ✅ ScannerConfig import successful")

    try:
        config = ScannerConfig.from_env()
        print("   ✅ ScannerConfig created from environment")
    except Exception as e:
        print(f"   ⚠️  ScannerConfig from_env() warning: {e}")

    risk_config = RiskFrameworkConfig()
    print("   ✅ RiskFrameworkConfig created with defaults")
    print(f"      - MIN_SPECIALIZATION_SCORE: {risk_config.MIN_SPECIALIZATION_SCORE}")
    print(f"      - MAX_CATEGORIES: {risk_config.MAX_CATEGORIES}")
    print(f"      - CATEGORY_WEIGHT: {risk_config.CATEGORY_WEIGHT}")
    print(f"      - MARTINGALE_THRESHOLD: {risk_config.MARTINGALE_THRESHOLD}")
    print(f"      - MARTINGALE_LIMIT: {risk_config.MARTINGALE_LIMIT}")
    print(f"      - BEHAVIOR_WEIGHT: {risk_config.BEHAVIOR_WEIGHT}")
    print(f"      - martingale: {risk_config.MARTINGALE}")
    print(f"      - loss chasing: {risk_config.LOSS_CHASING}")
    print(f"      - MARKET_MAKER_HOLD_TIME: {risk_config.MARKET_MAKER_HOLD_TIME}")
    print(f"      - MARKET_MAKER_WIN_RATE: {risk_config.MARKET_MAKER_WIN_RATE}")
    print(f"      - STRUCTURE_WEIGHT: {risk_config.STRUCTURE_WEIGHT}")
    print(f"      - market maker: {risk_config.MARKET_MAKER}")
    print(f"      - viral wallet: {risk_config.VIRAL_WALLET}")
    print(f"      - TARGET_WALLET_SCORE: {risk_config.TARGET_WALLET_SCORE}")
    print(f"      - WATCHLIST_SCORE: {risk_config.WATCHLIST_SCORE}")

    print("\n✅ All imports validated successfully")

except Exception as e:
    print(f"❌ Validation failed: {e}")
    sys.exit(1)

EOF

# Check exit code
if [ $? -ne 0 ]; then
    echo "\n❌ Validation failed. Exiting."
    exit 1
fi

# 7. Create test wallet samples file
echo "📋 7. Creating test wallet samples..."
cat > tests/integration/test_data/real_wallet_samples.json << 'EOF'
{
  "test_wallets": [
    {
      "address": "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
      "category": "US_POLITICS",
      "win_rate": 0.68,
      "roi_30d": 22.5,
      "max_drawdown": 0.18,
      "avg_hold_time_hours": 48,
      "trade_count": 150,
      "trades": [
        {"category": "US_POLITICS", "amount": 150.0, "pnl": 15.0},
        {"category": "US_POLITICS", "amount": 200.0, "pnl": -10.0},
        {"category": "US_POLITICS", "amount": 180.0, "pnl": 20.0},
        {"category": "US_POLITICS", "amount": 175.0, "pnl": -5.0}
      ]
    },
    {
      "address": "0x8a5d7f382763a2a954e85c8d89a0e3f4a9c5f3b8",
      "category": "CRYPTO",
      "win_rate": 0.72,
      "roi_30d": 18.3,
      "max_drawdown": 0.22,
      "avg_hold_time_hours": 24,
      "trade_count": 85,
      "trades": [
        {"category": "CRYPTO", "amount": 120.0, "pnl": 10.0},
        {"category": "CRYPTO", "amount": 140.0, "pnl": -8.0},
        {"category": "CRYPTO", "amount": 130.0, "pnl": 15.0},
        {"category": "CRYPTO", "amount": 125.0, "pnl": -5.0}
      ]
    }
  ]
}
EOF

echo "   ✅ Test wallet samples created"

# 8. Summary
echo "================================================================================"
echo "✅ TEST ENVIRONMENT SETUP COMPLETE"
echo "================================================================================"
echo ""
echo "Environment Variables:"
echo "  TEST_ENV=$TEST_ENV"
echo "  USE_TESTNET=$USE_TESTNET"
echo "  DRY_RUN=$DRY_RUN"
echo "  MAX_DAILY_LOSS=$MAX_DAILY_LOSS"
echo "  MAX_POSITION_SIZE=$MAX_POSITION_SIZE"
echo "  SCAN_INTERVAL_SECONDS=$SCAN_INTERVAL_SECONDS"
echo ""
echo "Python:"
echo "  Version: $PYTHON_VERSION"
echo "  Path: $(which python3)"
echo "  Virtualenv: $VIRTUAL_ENV"
echo ""
echo "Next Steps:"
echo "  1. Run validation: python3 scripts/validate_scanner_implementation.py"
echo "  2. Run scanner benchmark: python3 scripts/benchmark_high_performance_scanner.py --wallets 1000 --verbose"
echo "  3. Run memory benchmark: python3 scripts/benchmark_memory_usage.py --duration 300"
echo "  4. Run risk benchmark: python3 scripts/benchmark_risk_management.py --wallets 2000"
echo ""
echo "================================================================================"
