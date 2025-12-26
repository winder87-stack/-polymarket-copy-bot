# Monitoring Setup Guide for Polymarket Copy Bot

## Overview

This guide provides comprehensive instructions for setting up the native monitoring solution for the Polymarket Copy Bot, including system metrics, application monitoring, alerting, dashboards, and enhanced logging.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [System Monitoring](#system-monitoring)
5. [Application Monitoring](#application-monitoring)
6. [Alerting System](#alerting-system)
7. [Dashboard Setup](#dashboard-setup)
8. [Enhanced Logging](#enhanced-logging)
9. [Integration](#integration)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

```bash
# Ubuntu/Debian-based systems
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv curl wget jq

# Install monitoring dependencies
sudo apt-get install -y sysstat iotop htop ncdu

# Optional: For web dashboard
pip install flask flask-cors plotly pandas

# Optional: For enhanced alerting
pip install requests  # For webhook notifications
```

### Python Dependencies

```bash
# Install monitoring packages
pip install psutil plotly flask flask-cors pandas

# For enhanced logging
pip install structlog python-json-logger
```

### System Configuration

```bash
# Enable sysstat collection
sudo sed -i 's/ENABLED="false"/ENABLED="true"/' /etc/default/sysstat
sudo systemctl enable sysstat
sudo systemctl start sysstat

# Configure log rotation for monitoring logs
sudo tee /etc/logrotate.d/polymarket-monitoring << 'EOF'
/home/polymarket-bot/polymarket-copy-bot/logs/monitoring/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 polymarket-bot polymarket-bot
    postrotate
        systemctl reload polymarket-bot.service || true
    endscript
}
EOF
```

## Installation

### 1. Clone and Setup Project

```bash
# Navigate to project directory
cd /home/polymarket-bot/polymarket-copy-bot

# Make scripts executable
chmod +x scripts/system_monitor.py
chmod +x scripts/application_monitor.py
chmod +x scripts/alerting_system.py
chmod +x scripts/terminal_dashboard.py
chmod +x scripts/web_dashboard.py
chmod +x scripts/enhanced_logging.py
```

### 2. Create Monitoring Directories

```bash
# Create monitoring directories
sudo mkdir -p /home/polymarket-bot/polymarket-copy-bot/{monitoring,dashboards,alerts}
sudo chown -R polymarket-bot:polymarket-bot /home/polymarket-bot/polymarket-copy-bot/{monitoring,dashboards,alerts}
```

### 3. Install Python Dependencies

```bash
# Activate virtual environment
source /home/polymarket-bot/polymarket-copy-bot/venv/bin/activate

# Install monitoring packages
pip install psutil plotly flask flask-cors pandas requests

# For enhanced logging
pip install structlog python-json-logger
```

## Configuration

### System Monitor Configuration

```python
# scripts/system_monitor.py configuration
SYSTEM_CONFIG = {
    "collection_interval": 5,  # seconds
    "history_size": 1000,      # data points
    "alert_thresholds": {
        "cpu_percent": 80,
        "memory_percent": 85,
        "disk_percent": 90,
        "load_average": 4.0
    }
}
```

### Application Monitor Configuration

```python
# scripts/application_monitor.py configuration
APP_CONFIG = {
    "trade_success_threshold": 80,  # percent
    "api_rate_limit_threshold": 75, # percent
    "latency_warning_threshold": 5000,  # ms
    "circuit_breaker_enabled": True
}
```

### Alerting System Configuration

```python
# scripts/alerting_system.py configuration
ALERT_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "alerts@company.com",
    "telegram_bot_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id": "YOUR_CHAT_ID",
    "email_recipients": ["admin@company.com"],
    "cooldown_minutes": 5,
    "escalation_threshold": 3
}
```

### Enhanced Logging Configuration

```python
# scripts/enhanced_logging.py configuration
LOG_CONFIG = {
    "default_level": "INFO",
    "json_format": True,
    "correlation_ids": True,
    "anomaly_detection": True,
    "log_rotation": {
        "max_bytes": 10*1024*1024,  # 10MB
        "backup_count": 5
    }
}
```

## System Monitoring

### Start System Monitoring

```bash
# Start background system monitoring
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/system_monitor.py monitor --interval 5 &
```

### System Metrics Collection

The system monitor collects:

- **CPU Usage**: Percentage and load averages
- **Memory Usage**: RAM and swap utilization
- **Disk I/O**: Read/write rates and space usage
- **Network I/O**: Bandwidth consumption
- **File Descriptors**: Process limits and usage
- **Process Statistics**: Count and thread information

### System Monitor Commands

```bash
# Get current snapshot
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/system_monitor.py snapshot

# Monitor specific processes
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/system_monitor.py processes --process python

# Check for alerts
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/system_monitor.py alerts

# Continuous monitoring
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/system_monitor.py monitor
```

### System Metrics Output

```
System Metrics Snapshot (2025-01-25 10:30:15):
  CPU: 45.2% (Load: 1.25)
  Memory: 67.8% (5.4GB used)
  Disk: 72.3% (145.8GB used)
  Network: RX 2.4MB/s, TX 1.8MB/s
  File Descriptors: 245/1024
  Processes: 184, Threads: 450
```

## Application Monitoring

### Start Application Monitoring

```bash
# Start background application monitoring
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/application_monitor.py monitor &
```

### Application Metrics Tracked

- **Trade Execution**: Success rates, latency, volumes
- **API Usage**: Rate limits, response times, error rates
- **Circuit Breaker**: Activation status and frequency
- **Wallet Metrics**: Balance monitoring and transaction counts

### Application Monitor Commands

```bash
# Get current metrics
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/application_monitor.py snapshot

# View trade metrics
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/application_monitor.py trades

# Check API metrics
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/application_monitor.py api

# Monitor circuit breaker
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/application_monitor.py circuit-breaker
```

### Application Metrics Output

```
Application Metrics Snapshot:
  Trades: 1247 total, 95.4% success
  Latency: 2340ms avg
  API: 5672 requests, 68% rate limit
  Circuit Breaker: INACTIVE
```

## Alerting System

### Configure Alert Channels

#### Email Configuration

```bash
# Configure SMTP settings in environment
cat >> /home/polymarket-bot/polymarket-copy-bot/.env << EOF
# Alerting Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@company.com
SMTP_PASS=your_app_password
ALERT_EMAIL=admin@company.com
EOF
```

#### Telegram Configuration

```bash
# Configure Telegram bot
cat >> /home/polymarket-bot/polymarket-copy-bot/.env << EOF
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
EOF
```

### Alert Rule Configuration

```python
# Custom alert rules in alerting_system.py
from scripts.alerting_system import AlertRule

custom_rules = [
    AlertRule(
        name="Custom Trade Alert",
        category="APPLICATION",
        severity="MEDIUM",
        condition=lambda m: m.get('trade_volume', 0) > 1000,
        message_template="High trade volume detected: {trade_volume} trades",
        notification_channels=["telegram"]
    )
]

for rule in custom_rules:
    alerting_system.add_alert_rule(rule)
```

### Alerting Commands

```bash
# Check for alerts
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/alerting_system.py check

# List active alerts
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/alerting_system.py list-active

# List alert history
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/alerting_system.py list-history --hours 24

# Resolve alert
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/alerting_system.py resolve --alert-id alert_001

# Test notifications
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/alerting_system.py test
```

### Alert Severities and Escalation

| Severity | Description | Escalation | Channels |
|----------|-------------|------------|----------|
| **CRITICAL** | Service down, data loss | Immediate | Email + SMS + Telegram |
| **HIGH** | Service degraded | < 15 min | Email + Telegram |
| **MEDIUM** | Performance issues | < 1 hour | Email |
| **LOW** | Minor issues | < 4 hours | Log only |

## Dashboard Setup

### Terminal Dashboard

#### Start Terminal Dashboard

```bash
# Start interactive terminal dashboard
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/terminal_dashboard.py
```

#### Terminal Dashboard Controls

```
┌─────────────────────────────────────────────────────────┐
│ 🚀 Polymarket Copy Bot - Monitoring Dashboard          │
├─────────────────────────────────────────────────────────┤
│ [O]verview [S]ystem [A]pplication [L]erts [G]ogs [Q]uit │
│                                                         │
│ System Resources:                                       │
│   CPU: 45.2% (Load: 1.25)                              │
│   Memory: 67.8% (5.4GB used)                           │
│   Disk: 72.3% (145.8GB used)                           │
│                                                         │
│ Trading Performance:                                    │
│   Total Trades: 1247                                    │
│   Success Rate: 95.4%                                   │
│   Avg Latency: 2340ms                                   │
└─────────────────────────────────────────────────────────┘
```

#### Dashboard Views

- **Overview**: System and application summary
- **System**: Detailed CPU, memory, disk, network metrics
- **Application**: Trade performance, API usage, circuit breaker
- **Alerts**: Active alerts and historical data
- **Logs**: Real-time log streaming

### Web Dashboard

#### Start Web Dashboard

```bash
# Create dashboard templates
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/web_dashboard.py --create-templates

# Start web dashboard
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/web_dashboard.py --port 8080
```

#### Access Web Dashboard

Open browser to: `http://localhost:8080`

#### Web Dashboard Features

- **Real-time Metrics**: Live updating charts and graphs
- **Historical Data**: Time-series analysis with Plotly
- **Alert Management**: View and acknowledge alerts
- **Log Search**: Advanced log filtering and search
- **API Endpoints**: RESTful API for external integration

## Enhanced Logging

### Setup Enhanced Logging

```bash
# Setup enhanced logging system
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/enhanced_logging.py setup --level INFO
```

### Logger Usage in Code

```python
from scripts.enhanced_logging import get_logger, CorrelationContext

# Get structured logger
logger = get_logger("polymarket.trade")

# Use correlation context
with CorrelationContext() as ctx:
    logger.info("Starting trade execution", extra={
        "trade_id": "12345",
        "amount": 100,
        "symbol": "BTC"
    })

    # Nested operations maintain correlation
    logger.info("Validating trade parameters")
    logger.info("Executing trade")
```

### Log Analysis Commands

```bash
# Get log statistics
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/enhanced_logging.py stats

# Search logs
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/enhanced_logging.py search --query "ERROR" --hours 24

# Export logs
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/enhanced_logging.py export --filename incident_logs --hours 24

# Change log level at runtime
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/enhanced_logging.py set-level --logger polymarket.app --new-level DEBUG

# Check for anomalies
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/enhanced_logging.py anomalies
```

### JSON Log Format

```json
{
  "timestamp": "2025-01-25T10:30:15.123456",
  "level": "INFO",
  "logger": "polymarket.trade",
  "message": "Trade executed successfully",
  "module": "trade_executor",
  "function": "execute_trade",
  "line": 156,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "trade_id": "12345",
  "amount": 100,
  "symbol": "BTC",
  "latency_ms": 2340
}
```

## Integration

### Cron Job Setup

```bash
# System monitoring every 5 minutes
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "# System monitoring"; } | crontab -u polymarket-bot -
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "*/5 * * * * /home/polymarket-bot/polymarket-copy-bot/scripts/system_monitor.py snapshot >> /home/polymarket-bot/polymarket-copy-bot/logs/monitoring/system.log 2>&1"; } | crontab -u polymarket-bot -

# Health checks every minute
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "# Health monitoring"; } | crontab -u polymarket-bot -
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "*/1 * * * * /home/polymarket-bot/polymarket-copy-bot/scripts/health_monitor.sh production quick >> /home/polymarket-bot/polymarket-copy-bot/logs/monitoring/health.log 2>&1"; } | crontab -u polymarket-bot -

# Alert checking every 2 minutes
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "# Alert monitoring"; } | crontab -u polymarket-bot -
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "*/2 * * * * /home/polymarket-bot/polymarket-copy-bot/scripts/alerting_system.py check >> /home/polymarket-bot/polymarket-copy-bot/logs/monitoring/alerts.log 2>&1"; } | crontab -u polymarket-bot -
```

### Systemd Integration

```bash
# Create monitoring service
sudo tee /etc/systemd/system/polymarket-monitoring.service << EOF
[Unit]
Description=Polymarket Copy Bot Monitoring
After=polymarket-bot.service
Requires=polymarket-bot.service

[Service]
Type=simple
User=polymarket-bot
Group=polymarket-bot
WorkingDirectory=/home/polymarket-bot/polymarket-copy-bot
ExecStart=/home/polymarket-bot/polymarket-copy-bot/venv/bin/python /home/polymarket-bot/polymarket-copy-bot/scripts/web_dashboard.py --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start monitoring service
sudo systemctl daemon-reload
sudo systemctl enable polymarket-monitoring
sudo systemctl start polymarket-monitoring
```

### Log Aggregation

```bash
# Configure rsyslog for log aggregation
sudo tee /etc/rsyslog.d/50-polymarket.conf << EOF
# Polymarket log aggregation
:programname, startswith, "polymarket" /var/log/polymarket/all.log
& stop
EOF

sudo systemctl restart rsyslog
```

## Troubleshooting

### Common Issues

#### Monitoring Not Starting

```bash
# Check permissions
ls -la /home/polymarket-bot/polymarket-copy-bot/scripts/

# Check Python path
sudo -u polymarket-bot which python3
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/venv/bin/python --version

# Check dependencies
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/venv/bin/python -c "import psutil; print('psutil OK')"
```

#### Dashboard Not Loading

```bash
# Check web dashboard logs
sudo journalctl -u polymarket-monitoring -n 50

# Check port availability
sudo netstat -tlnp | grep :8080

# Test dashboard manually
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/web_dashboard.py --port 8080 --debug
```

#### Alerts Not Working

```bash
# Test email configuration
echo "Test email" | mail -s "Test Alert" admin@company.com

# Test Telegram bot
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"

# Check alert logs
tail -50 /home/polymarket-bot/polymarket-copy-bot/logs/monitoring/alerts.log
```

#### High Resource Usage

```bash
# Check monitoring processes
ps aux | grep -E "(monitor|dashboard)" | grep -v grep

# Check log file sizes
du -sh /home/polymarket-bot/polymarket-copy-bot/logs/

# Reduce monitoring frequency
# Edit crontab to increase intervals
sudo crontab -u polymarket-bot -e
```

### Performance Optimization

```bash
# Reduce monitoring frequency for production
# Change cron intervals from */1 to */5

# Enable log compression
sudo logrotate -f /etc/logrotate.d/polymarket-*

# Monitor monitoring resource usage
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/system_monitor.py processes --process python
```

### Recovery Procedures

#### Reset Monitoring System

```bash
# Stop all monitoring processes
sudo pkill -f "monitor\|dashboard"
sudo systemctl stop polymarket-monitoring

# Clear monitoring logs
sudo rm -f /home/polymarket-bot/polymarket-copy-bot/logs/monitoring/*.log

# Restart monitoring
sudo systemctl start polymarket-monitoring
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/system_monitor.py monitor &
```

#### Rebuild Dashboard Templates

```bash
# Remove old templates
sudo rm -rf /home/polymarket-bot/polymarket-copy-bot/templates/
sudo rm -rf /home/polymarket-bot/polymarket-copy-bot/static/

# Recreate templates
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/web_dashboard.py --create-templates
```

## Dashboard Screenshots

### Terminal Dashboard Overview

```
┌─ Polymarket Copy Bot - Monitoring Dashboard ──────────────────────┐
│ [O]verview [S]ystem [A]pplication [L]erts [G]ogs [Q]uit │ 10:30:15 │
├─────────────────────────────────────────────────────────────────────┤
│ System Resources:                                                  │
│   ● CPU: 45.2% (Load: 1.25)                                       │
│   ● Memory: 67.8% (5.4GB used)                                    │
│   ● Disk: 72.3% (145.8GB used)                                    │
│   ● Network: ↓2.4 ↑1.8 MB/s                                       │
│                                                                    │
│ Trading Performance:                                               │
│   ● Total Trades: 1,247                                            │
│   ● Success Rate: 95.4%                                            │
│   ● Avg Latency: 2,340ms                                           │
│   ● API Usage: 68%                                                 │
│                                                                    │
│ Active Alerts:                                                     │
│   ⚠️  WARNING: High Memory Usage (67.8%)                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Web Dashboard Overview

**System Resource Charts:**
- CPU usage over time (line chart)
- Memory utilization (area chart)
- Disk space trends (bar chart)
- Network I/O rates (combined chart)

**Trading Performance:**
- Success rate percentage (gauge chart)
- Trade latency distribution (histogram)
- API rate limit usage (progress bar)
- Active alerts summary (table)

**Real-time Features:**
- Auto-refresh every 30 seconds
- Interactive chart zooming
- Alert acknowledgment interface
- Log search and filtering

### Alert Management Interface

**Active Alerts Table:**
- Severity indicators (color-coded)
- Alert description and timestamp
- Acknowledge/dismiss actions
- Escalation status

**Alert History:**
- Timeline view of past alerts
- Filter by severity and time range
- Export capabilities
- Trend analysis

---

**Version**: 1.0.0
**Last Updated**: December 25, 2025
**Compatibility**: Native Linux deployment
**Resource Usage**: < 2% CPU, < 100MB RAM
