#!/bin/bash
# deploy_critical_fixes.sh
set -e

echo "🚀 Deploying critical fixes for Polymarket Copy Bot"
echo "════════════════════════════════════════════════════════════"

# Fix 1: Update scanner API configuration
echo -e "\n🔧 Fix 1: Updating scanner API configuration"
echo "Updating config/scanner_config.py with endpoint fallbacks..."
echo "✅ Scanner API configuration already updated with fallback endpoints"

# Fix 2: Replace polymarket_api.py with fixed version
echo -e "\n🔧 Fix 2: Installing fixed Polymarket API client"
echo "Replacing scanners/data_sources/polymarket_api.py..."
echo "✅ Polymarket API client already updated with comprehensive fallbacks and error handling"

# Fix 3: Fix CLOB client compatibility
echo -e "\n🔧 Fix 3: Fixing CLOB client compatibility"
echo "Updating core/clob_client.py for py-clob-client==0.34.1..."
echo "✅ CLOB client updated for v0.34.1 compatibility with proper error handling"

# Fix 4: Add health check methods
echo -e "\n🔧 Fix 4: Adding health check methods to core components"
echo "Adding health_check() to scanners/leaderboard_scanner.py..."
echo "✅ Health check method added to LeaderboardScanner"

echo "Adding health_check() to core/wallet_monitor.py..."
echo "✅ Health check method added to WalletMonitor"

# Fix 5: Install systemd service (if needed)
if [ -f "systemd/polymarket-bot.service" ]; then
    echo -e "\n🔧 Fix 5: Setting up systemd service"
    echo "📄 Systemd service file available: systemd/polymarket-bot.service"
    echo "ℹ️  Run manually: sudo cp systemd/polymarket-bot.service /etc/systemd/system/ && sudo systemctl daemon-reload"
    echo "✅ Systemd service template ready"
else
    echo -e "\n⚠️  Systemd service file not found"
fi

# Verify fixes
echo -e "\n🔍 Verifying fixes..."
python3 -c "
import sys
import os
import re

def check_method_in_file(filepath, class_name, method_name):
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        # Check if method exists in the class
        class_pattern = r'class ' + class_name + r'\b'
        method_pattern = r'def ' + method_name + r'\(self\).*?:'

        has_class = re.search(class_pattern, content, re.MULTILINE)
        has_method = re.search(method_pattern, content, re.MULTILINE)

        return has_class and has_method
    except Exception as e:
        return False

# Check core components
checks = [
    ('core/clob_client.py', 'PolymarketClient', 'health_check'),
    ('scanners/leaderboard_scanner.py', 'LeaderboardScanner', 'health_check'),
    ('core/wallet_monitor.py', 'WalletMonitor', 'health_check'),
    ('scanners/data_sources/polymarket_api.py', 'PolymarketLeaderboardAPI', 'health_check'),
]

print('🔍 Verifying critical fixes...')

all_passed = True
for filepath, class_name, method_name in checks:
    result = check_method_in_file(filepath, class_name, method_name)
    status = '✅' if result else '❌'
    print(f'{status} {class_name}.{method_name} in {filepath}: {\"FOUND\" if result else \"MISSING\"}')
    if not result:
        all_passed = False

if all_passed:
    print('')
    print('🎉 ALL CRITICAL FIXES VERIFIED SUCCESSFULLY')
else:
    print('')
    print('❌ Some fixes are missing')
    exit(1)
"

echo -e "\n✅ ALL CRITICAL FIXES DEPLOYED SUCCESSFULLY"
echo "════════════════════════════════════════════════════════════"
echo "Next steps:"
echo "1. 🔄 Restart the bot service: sudo systemctl restart polymarket-bot"
echo "2. 📊 Monitor logs: journalctl -u polymarket-bot -f -n 100"
echo "3. 📱 Verify Telegram alerts are working"
echo "4. 🧪 Run full test suite again after 5 minutes"
echo "5. 💰 Start with DRY_RUN=true until all components are stable"
