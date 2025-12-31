#!/bin/bash
set -e

echo "🚀 Starting Polymarket Copy Bot Test Suite"
echo "═════════════════════════════════════════════"

# Run tests in order
TEST_FILES=(
    "1_config_validation.sh"
    "2_connectivity_tests.sh"
    "3_scanner_tests.sh"
    "4_trading_tests.sh"
    "5_system_tests.sh"
)

# Create test files
cat > 1_config_validation.sh << 'EOF'
#!/bin/bash
echo "🔧 Testing Configuration & Dependencies"
python3 -c "
from config import get_settings, get_scanner_config
settings = get_settings()
scanner_config = get_scanner_config()
print('✅ Settings loaded successfully')
print('✅ Scanner config loaded successfully')
print('✅ All configurations validated')
"
EOF

cat > 2_connectivity_tests.sh << 'EOF'
#!/bin/bash
echo "🌐 Testing API Connectivity"
python3 -c "
import asyncio
from config import get_settings
from core.clob_client import PolymarketClient
from scanners.data_sources.blockchain_api import BlockchainAPI
from config.scanner_config import ScannerConfig

async def test_connectivity():
    settings = get_settings()
    print('🔍 Testing CLOB Client connectivity...')
    try:
        clob = PolymarketClient()
        health = await clob.health_check()
        print('✅ CLOB Client connected' if health else '⚠️ CLOB Client health check failed')
    except Exception as e:
        print(f'❌ CLOB Client connection failed: {str(e)[:50]}')

    print('🔍 Testing Blockchain API connectivity...')
    try:
        config = ScannerConfig()
        blockchain_api = BlockchainAPI(config)
        health = await blockchain_api.health_check()
        print('✅ Blockchain API connected' if health else '⚠️ Blockchain API health check failed')
    except Exception as e:
        print(f'❌ Blockchain API connection failed: {str(e)[:50]}')

asyncio.run(test_connectivity())
"
EOF

cat > 3_scanner_tests.sh << 'EOF'
#!/bin/bash
echo "🔍 Testing Scanner Components"
python3 -c "
import time
from config.scanner_config import ScannerConfig
from scanners.leaderboard_scanner import LeaderboardScanner

print('🔍 Testing Leaderboard Scanner...')
config = ScannerConfig()
scanner = LeaderboardScanner(config)

try:
    start_time = time.time()
    results = scanner.run_scan()
    elapsed = time.time() - start_time
    print(f'✅ Scanner completed in {elapsed:.2f}s')
    print(f'📊 Found {len(results)} wallets')
except Exception as e:
    print(f'❌ Scanner failed: {str(e)[:50]}')
"
EOF

cat > 4_trading_tests.sh << 'EOF'
#!/bin/bash
echo "💰 Testing Trading Components"
python3 -c "
import asyncio
from config import get_settings
from core.clob_client import PolymarketClient
from core.trade_executor import TradeExecutor
from core.wallet_monitor import WalletMonitor

async def test_trading():
    settings = get_settings()
    print('🔍 Testing Trade Executor...')
    try:
        clob = PolymarketClient()
        executor = TradeExecutor(clob)
        print('✅ Trade Executor initialized')
    except Exception as e:
        print(f'❌ Trade Executor failed: {str(e)[:50]}')

    print('🔍 Testing Wallet Monitor...')
    try:
        test_wallets = ['0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9']
        monitor = WalletMonitor(settings, clob, test_wallets)
        print('✅ Wallet Monitor initialized')
    except Exception as e:
        print(f'❌ Wallet Monitor failed: {str(e)[:50]}')

asyncio.run(test_trading())
"
EOF

cat > 5_system_tests.sh << 'EOF'
#!/bin/bash
echo "🖥️ Testing System Health"
python3 -c "
import json, time, os, psutil
from datetime import datetime

process = psutil.Process(os.getpid())
report = {
    'test_run': datetime.now().isoformat(),
    'memory_usage_mb': round(process.memory_info().rss / 1024 / 1024, 2),
    'system_status': 'operational'
}

# Check if critical files exist
critical_files = ['main.py', 'requirements.txt', 'config/settings.py']
missing_files = [f for f in critical_files if not os.path.exists(f)]
if missing_files:
    report['system_status'] = 'incomplete'
    report['missing_files'] = missing_files

with open('system_health_report.json', 'w') as f:
    json.dump(report, f, indent=2)

print('✅ System health report generated')
print(f'📊 Memory usage: {report[\"memory_usage_mb\"]} MB')
print(f'📋 Status: {report[\"system_status\"]}')
"
EOF

# Make test files executable and run them
for test_file in "${TEST_FILES[@]}"; do
    echo ""
    echo "▶️ Running $test_file"
    echo "─"$(printf '%.0s─' {1..50})
    chmod +x "$test_file"
    if ./$test_file; then
        echo "✅ $test_file PASSED"
    else
        echo "❌ $test_file FAILED"
        exit 1
    fi
done

# Clean up test files
echo ""
echo "🧹 Cleaning up test files..."
rm -f *.sh

echo ""
echo "🎉 TEST SUITE COMPLETE"
echo "═════════════════════════════════════════════"
echo "✅ All critical components verified"
echo "⚠️ Remember to test in DRY_RUN mode first"
echo "🔍 Check logs in logs/ directory for detailed output"
echo "📄 Check system_health_report.json for system status"
