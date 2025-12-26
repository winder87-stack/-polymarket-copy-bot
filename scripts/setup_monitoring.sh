#!/bin/bash
# Setup script for Polymarket Bot Monitoring System
# ==================================================
#
# This script sets up the comprehensive monitoring system including:
# - Security scanning tools
# - Performance benchmarking
# - Alert health monitoring
# - Automated scheduling
# - Report generation
#
# ==================================================

set -e

echo "📊 Setting up Polymarket Bot Monitoring System..."
echo "=================================================="

# Check if running as root
if [ "$(id -u)" != "0" ]; then
   echo "❌ This script must be run as root" 1>&2
   exit 1
fi

# Configuration
PROJECT_DIR="/home/polymarket-bot/polymarket-copy-bot"
USER_NAME="polymarket-bot"
VENV_DIR="$PROJECT_DIR/venv"

echo "📋 Configuration:"
echo "   Project dir: $PROJECT_DIR"
echo "   User: $USER_NAME"
echo "   Monitoring: Comprehensive system"

# Update system
echo "🔄 Updating system packages..."
apt update
DEBIAN_FRONTEND=noninteractive apt upgrade -y

# Install monitoring dependencies
echo "📦 Installing monitoring dependencies..."
apt install -y \
    python3-dev \
    build-essential \
    git \
    curl \
    jq \
    cron \
    logrotate \
    prometheus-node-exporter \
    unattended-upgrades

# Install Python monitoring packages
echo "🐍 Installing Python monitoring packages..."
sudo -u "$USER_NAME" bash -c "cd '$PROJECT_DIR' && source '$VENV_DIR/bin/activate' && pip install \
    bandit \
    safety \
    psutil \
    pytest \
    pytest-cov \
    pytest-asyncio \
    black \
    isort \
    flake8 \
    mypy \
    pre-commit"

# Set up monitoring directories
echo "📁 Setting up monitoring directories..."
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/monitoring"
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/monitoring/security"
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/monitoring/performance"
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/monitoring/alert_health"
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/monitoring/reports"
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/monitoring/logs"
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/monitoring/baselines"
sudo -u "$USER_NAME" mkdir -p "$PROJECT_DIR/monitoring/config"

# Set permissions
chown -R "$USER_NAME:$USER_NAME" "$PROJECT_DIR/monitoring"
chmod 750 "$PROJECT_DIR/monitoring"
chmod 750 "$PROJECT_DIR/monitoring"/*

# Install systemd monitoring service and timer
echo "⚙️ Installing systemd monitoring services..."
SERVICE_FILE="/etc/systemd/system/polymarket-monitoring.service"
TIMER_FILE="/etc/systemd/system/polymarket-monitoring.timer"

cp "$PROJECT_DIR/systemd/polymarket-monitoring.service" "$SERVICE_FILE"
cp "$PROJECT_DIR/systemd/polymarket-monitoring.timer" "$TIMER_FILE"

chmod 644 "$SERVICE_FILE"
chmod 644 "$TIMER_FILE"

# Reload systemd
systemctl daemon-reload

# Enable and start monitoring timer
echo "🔄 Enabling monitoring timer..."
systemctl enable polymarket-monitoring.timer
systemctl start polymarket-monitoring.timer

# Set up logrotate for monitoring logs
echo "📝 Setting up log rotation..."
cat > "/etc/logrotate.d/polymarket-monitoring" << 'EOF'
/home/polymarket-bot/polymarket-copy-bot/monitoring/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 polymarket-bot polymarket-bot
    postrotate
        systemctl reload polymarket-monitoring.service || true
    endscript
}
EOF

# Set up monitoring configuration
echo "⚙️ Setting up monitoring configuration..."
if [ ! -f "$PROJECT_DIR/monitoring/config/monitoring_config.json" ]; then
    sudo -u "$USER_NAME" bash -c "cd '$PROJECT_DIR' && source '$VENV_DIR/bin/activate' && python -c '
from monitoring.monitoring_config import monitoring_config
import json
config_file = \"monitoring/config/monitoring_config.json\"
with open(config_file, \"w\") as f:
    json.dump(monitoring_config.dict(), f, indent=2)
print(f\"✅ Monitoring configuration saved to {config_file}\")
'"
fi

# Set up initial baselines
echo "📊 Setting up initial performance baselines..."
sudo -u "$USER_NAME" bash -c "cd '$PROJECT_DIR' && source '$VENV_DIR/bin/activate' && python -c '
from monitoring.performance_benchmark import PerformanceBenchmark
import asyncio
import json

async def create_baseline():
    benchmark = PerformanceBenchmark()
    print(\"Running initial performance benchmark for baseline...\")
    results = await benchmark.run_full_benchmark()

    # Save as baseline
    baseline_file = \"monitoring/baselines/initial_baseline.json\"
    with open(baseline_file, \"w\") as f:
        json.dump(results, f, indent=2, default=str)

    print(f\"✅ Initial baseline saved to {baseline_file}\")
    return results

results = asyncio.run(create_baseline())
print(f\"Baseline created with {len(results.get(\"scenarios\", {}))} scenarios\")
'"

# Set up pre-commit hooks if in git repository
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "🔗 Setting up pre-commit hooks..."
    sudo -u "$USER_NAME" bash -c "cd '$PROJECT_DIR' && source '$VENV_DIR/bin/activate' && pre-commit install"

    if [ -f "$PROJECT_DIR/.pre-commit-config.yaml" ]; then
        echo "✅ Pre-commit hooks configured"
    fi
fi

# Test monitoring system
echo "🧪 Testing monitoring system..."
sudo -u "$USER_NAME" bash -c "cd '$PROJECT_DIR' && source '$VENV_DIR/bin/activate' && timeout 300 python monitoring/monitor_all.py --checks security --verbose"

if [ $? -eq 0 ]; then
    echo "✅ Monitoring system test completed successfully"
else
    echo "⚠️ Monitoring system test completed with warnings (this is normal for initial setup)"
fi

# Set up cron job as backup to systemd timer
echo "📅 Setting up backup cron job..."
CRON_JOB="0 2 * * * $USER_NAME cd $PROJECT_DIR && source $VENV_DIR/bin/activate && python monitoring/monitor_all.py --schedule cron-backup >> monitoring/logs/cron_monitoring.log 2>&1"

# Add to crontab if not already present
if ! crontab -u "$USER_NAME" -l 2>/dev/null | grep -q "monitor_all.py"; then
    (crontab -u "$USER_NAME" -l 2>/dev/null; echo "$CRON_JOB") | crontab -u "$USER_NAME" -
    echo "✅ Backup cron job added"
fi

# Create monitoring status script
echo "📊 Creating monitoring status script..."
cat > "$PROJECT_DIR/scripts/monitoring_status.sh" << 'EOF'
#!/bin/bash
# Monitoring Status Script
# ========================
#
# Shows the current status of all monitoring systems

echo "📊 Polymarket Bot Monitoring Status"
echo "==================================="

PROJECT_DIR="/home/polymarket-bot/polymarket-copy-bot"

# Service status
echo "🔧 Service Status:"
echo "  Main Bot: $(systemctl is-active polymarket-bot 2>/dev/null || echo 'unknown')"
echo "  Monitoring: $(systemctl is-active polymarket-monitoring.timer 2>/dev/null || echo 'unknown')"

# Recent monitoring runs
echo ""
echo "📋 Recent Monitoring Runs:"
if [ -f "$PROJECT_DIR/monitoring/reports/latest_monitoring_run.json" ]; then
    TIMESTAMP=$(jq -r '.timestamp' "$PROJECT_DIR/monitoring/reports/latest_monitoring_run.json" 2>/dev/null || echo "unknown")
    STATUS=$(jq -r '.summary.overall_status' "$PROJECT_DIR/monitoring/reports/latest_monitoring_run.json" 2>/dev/null || echo "unknown")
    ALERTS=$(jq -r '.summary.total_alerts' "$PROJECT_DIR/monitoring/reports/latest_monitoring_run.json" 2>/dev/null || echo "0")
    echo "  Last Run: $TIMESTAMP"
    echo "  Status: $STATUS"
    echo "  Alerts: $ALERTS"
else
    echo "  No monitoring runs found"
fi

# Security scan status
echo ""
echo "🔒 Security Scan Status:"
if [ -f "$PROJECT_DIR/monitoring/security/latest_security_scan.json" ]; then
    SCAN_TIME=$(jq -r '.timestamp' "$PROJECT_DIR/monitoring/security/latest_security_scan.json" 2>/dev/null || echo "unknown")
    VULNS=$(jq -r '.summary.total_issues' "$PROJECT_DIR/monitoring/security/latest_security_scan.json" 2>/dev/null || echo "0")
    echo "  Last Scan: $SCAN_TIME"
    echo "  Issues Found: $VULNS"
else
    echo "  No security scans found"
fi

# Performance benchmark status
echo ""
echo "📈 Performance Benchmark Status:"
if [ -f "$PROJECT_DIR/monitoring/performance/latest_benchmark.json" ]; then
    BENCH_TIME=$(jq -r '.timestamp' "$PROJECT_DIR/monitoring/performance/latest_benchmark.json" 2>/dev/null || echo "unknown")
    SCENARIOS=$(jq -r '.scenarios | length' "$PROJECT_DIR/monitoring/performance/latest_benchmark.json" 2>/dev/null || echo "0")
    echo "  Last Benchmark: $BENCH_TIME"
    echo "  Scenarios Run: $SCENARIOS"
else
    echo "  No performance benchmarks found"
fi

# Alert health status
echo ""
echo "🚨 Alert Health Status:"
if [ -f "$PROJECT_DIR/monitoring/alert_health/latest_health_check.json" ]; then
    HEALTH_TIME=$(jq -r '.timestamp' "$PROJECT_DIR/monitoring/alert_health/latest_health_check.json" 2>/dev/null || echo "unknown")
    OVERALL_HEALTH=$(jq -r '.overall_health' "$PROJECT_DIR/monitoring/alert_health/latest_health_check.json" 2>/dev/null || echo "unknown")
    echo "  Last Check: $HEALTH_TIME"
    echo "  Overall Health: $OVERALL_HEALTH"
else
    echo "  No alert health checks found"
fi

echo ""
echo "🎯 Quick Actions:"
echo "  Run full monitoring: sudo -u polymarket-bot $PROJECT_DIR/monitoring/monitor_all.py"
echo "  View latest report: cat $PROJECT_DIR/monitoring/reports/latest_monitoring_run.json | jq ."
echo "  Check service logs: journalctl -u polymarket-monitoring -f"
EOF

chmod +x "$PROJECT_DIR/scripts/monitoring_status.sh"

echo ""
echo "🎉 Monitoring system setup completed!"
echo "======================================"
echo ""
echo "📋 Next steps:"
echo "1. Review monitoring configuration:"
echo "   cat $PROJECT_DIR/monitoring/config/monitoring_config.json"
echo ""
echo "2. Check monitoring status:"
echo "   $PROJECT_DIR/scripts/monitoring_status.sh"
echo ""
echo "3. Run a manual monitoring check:"
echo "   sudo -u polymarket-bot $PROJECT_DIR/monitoring/monitor_all.py --verbose"
echo ""
echo "4. Verify automated monitoring:"
echo "   systemctl list-timers | grep polymarket"
echo ""
echo "🔍 Monitoring will run daily at 2 AM (with random delay)"
echo "📊 Reports saved to: $PROJECT_DIR/monitoring/reports/"
echo "🚨 Alerts sent via configured Telegram bot"
echo ""
echo "✅ MONITORING SYSTEM READY ✅"
