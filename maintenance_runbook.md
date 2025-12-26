# Maintenance Runbook for Polymarket Copy Trading Bot

## Overview

This runbook provides comprehensive procedures for maintaining the Polymarket Copy Trading Bot native deployment, including update procedures, monitoring, automated maintenance, and incident response.

## Table of Contents

1. [Emergency Contacts](#emergency-contacts)
2. [System Architecture](#system-architecture)
3. [Update Procedures](#update-procedures)
4. [Monitoring & Health Checks](#monitoring--health-checks)
5. [Automated Maintenance](#automated-maintenance)
6. [Incident Response](#incident-response)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)
9. [Maintenance Checklist](#maintenance-checklist)

## Emergency Contacts

### Primary Contacts

| Role | Name | Contact | Availability |
|------|------|---------|--------------|
| **System Administrator** | On-Call Admin | admin@company.com | 24/7 |
| **DevOps Lead** | DevOps Lead | devops@company.com | Business Hours |
| **Development Lead** | Dev Lead | devlead@company.com | Business Hours |
| **Management** | CTO | cto@company.com | Business Hours |

### Escalation Matrix

- **Level 1 (L1)**: System Administrator - First response, basic troubleshooting
- **Level 2 (L2)**: DevOps Team - Advanced troubleshooting, system issues
- **Level 3 (L3)**: Development Team - Application code issues
- **Level 4 (L4)**: Management - Business impact, external communication

### Emergency Communication

- **Phone**: +1 (555) 123-4567 (On-call Admin)
- **Email**: emergency@company.com
- **Slack**: #polymarket-emergency
- **PagerDuty**: Integrated with monitoring alerts

## System Architecture

### Component Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Application   │    │   Database      │
│   (nginx)       │────│   Server        │────│   (SQLite)      │
│                 │    │   (Python)      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Blockchain    │
                    │   RPC Nodes     │
                    └─────────────────┘
```

### Directory Structure

```
/home/polymarket-bot/polymarket-copy-bot/
├── scripts/                 # Maintenance scripts
│   ├── update_procedures.sh
│   ├── health_monitor.sh
│   ├── automated_maintenance.sh
│   └── incident_response.sh
├── logs/                    # Application logs
├── data/                    # Trade data and cache
├── backups/                 # Backup storage
├── security/               # Security monitoring
└── venv/                   # Python virtual environment
```

### Service Dependencies

- **systemd**: Service management
- **logrotate**: Log rotation
- **cron**: Scheduled maintenance
- **rsyslog**: System logging
- **auditd**: Security auditing

## Update Procedures

### Zero-Downtime Update Process

#### Pre-Update Checklist

```bash
# 1. Check current system status
sudo scripts/health_monitor.sh production comprehensive

# 2. Verify backup integrity
sudo scripts/backup_secure.sh production config
sudo scripts/backup_secure.sh production data

# 3. Check available resources
df -h /home/polymarket-bot/
free -h

# 4. Verify update package
ls -la /path/to/update/package/
```

#### Rolling Update Execution

```bash
# 1. Start update process
sudo scripts/update_procedures.sh production rolling latest

# 2. Monitor update progress
tail -f /home/polymarket-bot/polymarket-copy-bot/logs/update_production.log

# 3. Verify service health
sudo systemctl status polymarket-bot
sudo scripts/health_monitor.sh production quick
```

#### Post-Update Verification

```bash
# 1. Check service functionality
curl -f http://localhost:8000/health

# 2. Verify application logs
tail -50 /home/polymarket-bot/polymarket-copy-bot/logs/trade_*.log

# 3. Monitor for 15 minutes
watch -n 30 'sudo scripts/health_monitor.sh production quick'
```

### Rollback Procedures

#### Automatic Rollback

```bash
# Trigger automatic rollback
sudo scripts/update_procedures.sh production rollback /path/to/backup
```

#### Manual Rollback Steps

```bash
# 1. Stop service
sudo systemctl stop polymarket-bot

# 2. Restore from backup
sudo cp -r /path/to/backup/* /home/polymarket-bot/polymarket-copy-bot/

# 3. Reset permissions
sudo chown -R polymarket-bot:polymarket-bot /home/polymarket-bot/polymarket-copy-bot

# 4. Start service
sudo systemctl start polymarket-bot

# 5. Verify recovery
sudo scripts/health_monitor.sh production comprehensive
```

### Configuration Change Management

#### Configuration Update Process

```bash
# 1. Backup current configuration
cp /home/polymarket-bot/polymarket-copy-bot/.env /home/polymarket-bot/polymarket-copy-bot/.env.backup

# 2. Apply configuration changes
nano /home/polymarket-bot/polymarket-copy-bot/.env

# 3. Validate configuration
python3 -c "
import sys
sys.path.insert(0, '/home/polymarket-bot/polymarket-copy-bot')
from config.settings import settings
settings.validate_critical_settings()
print('Configuration validated')
"

# 4. Reload service
sudo systemctl reload polymarket-bot

# 5. Monitor for issues
sudo scripts/health_monitor.sh production comprehensive
```

#### Configuration Rollback

```bash
# Restore configuration backup
cp /home/polymarket-bot/polymarket-copy-bot/.env.backup /home/polymarket-bot/polymarket-copy-bot/.env

# Reload service
sudo systemctl reload polymarket-bot
```

### Dependency Update Workflow

#### Security Update Process

```bash
# 1. Check for vulnerabilities
python3 -m venv /tmp/check_env
source /tmp/check_env/bin/activate
pip install safety
safety check --file /home/polymarket-bot/polymarket-copy-bot/requirements.txt

# 2. Update dependencies
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/venv/bin/pip install --upgrade -r requirements.txt

# 3. Restart service
sudo systemctl restart polymarket-bot

# 4. Monitor for issues
sudo scripts/health_monitor.sh production comprehensive
```

## Monitoring & Health Checks

### Health Check Endpoints

#### System Health Check

```bash
# Comprehensive health check
sudo scripts/health_monitor.sh production comprehensive

# Quick health check
sudo scripts/health_monitor.sh production quick

# Check specific component
curl -s http://localhost:8000/health | jq .
```

#### Health Check Output Interpretation

```json
{
  "status": "healthy|degraded|unhealthy",
  "issues_found": 0,
  "warnings_found": 2,
  "checks_performed": [
    "service_status",
    "process_health",
    "resource_usage",
    "network_connectivity"
  ]
}
```

### Resource Monitoring

#### CPU and Memory Monitoring

```bash
# Real-time monitoring
watch -n 5 'ps aux | grep polymarket | head -5'

# Resource usage history
sar -u 1 10

# Memory analysis
free -h && vmstat 1 5
```

#### Disk Space Monitoring

```bash
# Check disk usage
df -h /home/polymarket-bot/

# Monitor log growth
du -sh /home/polymarket-bot/polymarket-copy-bot/logs/

# Clean old logs if needed
find /home/polymarket-bot/polymarket-copy-bot/logs/ -name "*.log.gz" -mtime +30 -delete
```

### Blockchain Sync Monitoring

#### RPC Connection Health

```bash
# Test RPC connectivity
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  https://polygon-rpc.com/

# Monitor connection count
netstat -t | grep :443 | wc -l

# Check for connection errors
journalctl -u polymarket-bot | grep -i "connection\|rpc\|timeout" | tail -10
```

## Automated Maintenance

### Cron Job Configuration

#### Daily Maintenance (2:00 AM)

```bash
# Add to crontab
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "# Daily maintenance"; } | crontab -u polymarket-bot -
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "0 2 * * * /home/polymarket-bot/polymarket-copy-bot/scripts/automated_maintenance.sh daily production"; } | crontab -u polymarket-bot -
```

#### Weekly Maintenance (Sundays 3:00 AM)

```bash
sudo crontab -u polymarket-staging -l 2>/dev/null | { cat; echo "0 3 * * 0 /home/polymarket-staging/polymarket-copy-bot/scripts/automated_maintenance.sh weekly staging"; } | crontab -u polymarket-staging -
```

#### Health Monitoring (Every 30 minutes)

```bash
sudo crontab -u root -l 2>/dev/null | { cat; echo "*/30 * * * * /home/polymarket-bot/polymarket-copy-bot/scripts/health_monitor.sh production comprehensive"; } | crontab -u root -
```

### Log Rotation Configuration

```bash
# Configure logrotate
sudo tee /etc/logrotate.d/polymarket-bot << 'EOF'
/home/polymarket-bot/polymarket-copy-bot/logs/*.log {
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

# Test log rotation
sudo logrotate -f /etc/logrotate.d/polymarket-bot
```

### Security Update Automation

#### Automated Security Scanning

```bash
# Weekly security scan
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "0 4 * * 1 /home/polymarket-bot/polymarket-copy-bot/scripts/automated_maintenance.sh security production"; } | crontab -u polymarket-bot -
```

### Database Optimization

#### SQLite Vacuum Operation

```bash
# Manual vacuum (run during maintenance window)
sudo -u polymarket-bot sqlite3 /home/polymarket-bot/polymarket-copy-bot/data/trade_history.db "VACUUM;"

# Check database integrity
sudo -u polymarket-bot sqlite3 /home/polymarket-bot/polymarket-copy-bot/data/trade_history.db "PRAGMA integrity_check;"
```

### Certificate Management

#### SSL Certificate Renewal

```bash
# Check certificate expiry
openssl x509 -in /path/to/certificate.pem -noout -enddate

# Renew certificate (if using Let's Encrypt)
certbot renew

# Reload services
sudo systemctl reload polymarket-bot
```

## Incident Response

### Incident Classification System

#### Severity Levels

| Severity | Description | Response Time | Escalation |
|----------|-------------|---------------|------------|
| **Critical** | Service down, data loss | Immediate | L1 → L2 → L4 |
| **High** | Service degraded, urgent | < 15 minutes | L1 → L2 → L3 |
| **Medium** | Performance issues | < 1 hour | L1 → L2 |
| **Low** | Minor issues | < 4 hours | L1 |

#### Incident Classification Script

```bash
# Automatic incident detection
sudo scripts/incident_response.sh auto production

# Manual incident declaration
sudo scripts/incident_response.sh manual production
```

### Escalation Procedures

#### Level 1 Response (System Administrator)

1. **Acknowledge alert** within 5 minutes
2. **Assess situation** using health checks
3. **Attempt basic recovery** (service restart, etc.)
4. **Escalate if unresolved** within 15 minutes

#### Level 2 Response (DevOps Team)

1. **Review system logs** and metrics
2. **Check infrastructure** components
3. **Perform advanced troubleshooting**
4. **Coordinate with development team** if needed

#### Level 3 Response (Development Team)

1. **Code review** for potential issues
2. **Database analysis** if applicable
3. **Blockchain connectivity** verification
4. **Hotfix development** if required

#### Level 4 Response (Management)

1. **Business impact assessment**
2. **Stakeholder communication**
3. **Resource allocation** for resolution
4. **Post-incident review** coordination

### Circuit Breaker Activation

#### Automatic Circuit Breaker

```bash
# Check circuit breaker status
ls -la /home/polymarket-bot/polymarket-copy-bot/.circuit_breaker_active

# Reset circuit breaker (manual)
sudo scripts/incident_response.sh circuit-breaker-reset production

# Verify reset
sudo systemctl status polymarket-bot
```

#### Circuit Breaker Recovery

```bash
# 1. Investigate root cause
sudo scripts/incident_response.sh evidence production

# 2. Apply fix
# (manual intervention based on investigation)

# 3. Reset circuit breaker
sudo scripts/incident_response.sh circuit-breaker-reset production

# 4. Monitor closely
watch -n 30 'sudo scripts/health_monitor.sh production quick'
```

### Post-Incident Review Template

#### Incident Review Checklist

```markdown
# Post-Incident Review: INC-20241225-143000

## Incident Summary
- **Date/Time**: YYYY-MM-DD HH:MM
- **Duration**: X hours Y minutes
- **Impact**: Description of impact
- **Severity**: Critical/High/Medium/Low

## Timeline
- **Detection**: When incident was detected
- **Response**: When response began
- **Resolution**: When incident was resolved
- **Recovery**: When service was fully recovered

## Root Cause Analysis
- **Primary Cause**: Detailed description
- **Contributing Factors**: List of contributing factors
- **Impact Analysis**: Why it happened

## Response Analysis
- **What went well**: Positive aspects
- **What went wrong**: Issues encountered
- **Improvements needed**: Areas for improvement

## Action Items
- [ ] **Immediate**: Actions completed during incident
- [ ] **Short-term**: Actions within 1 week
- [ ] **Medium-term**: Actions within 1 month
- [ ] **Long-term**: Actions for future prevention

## Prevention Measures
- **Monitoring improvements**: New alerts/monitors needed
- **Process changes**: Changes to procedures
- **Technical improvements**: Code/system changes needed

## Lessons Learned
- Key takeaways from incident
- Process improvements identified
- Training needs identified

## Attendees
- List of participants in review meeting

## Next Review Date
- Date for follow-up review if needed
```

## Backup & Recovery

### Backup Strategy

#### Automated Backup Schedule

- **Configuration backups**: Every 12 hours
- **Data backups**: Daily
- **Full backups**: Weekly
- **Retention**: 30 days for configs, 7 days for data, 3 months for full

#### Backup Commands

```bash
# Configuration backup
sudo scripts/backup_secure.sh production config

# Data backup
sudo scripts/backup_secure.sh production data

# Full backup
sudo scripts/backup_secure.sh production all
```

### Recovery Procedures

#### Configuration Recovery

```bash
# List available backups
sudo scripts/recovery_secure.sh list production

# Recover configuration
sudo scripts/recovery_secure.sh production config /path/to/config_backup.tar.gz

# Verify recovery
sudo scripts/health_monitor.sh production comprehensive
```

#### Data Recovery

```bash
# Recover trade data
sudo scripts/recovery_secure.sh production data /path/to/data_backup.tar.gz

# Verify data integrity
sudo -u polymarket-bot sqlite3 /home/polymarket-bot/polymarket-copy-bot/data/trade_history.db "PRAGMA integrity_check;"
```

#### Full System Recovery

```bash
# Complete system recovery
sudo scripts/recovery_secure.sh production all /path/to/full_backup.tar.gz

# Reconfigure environment
sudo nano /home/polymarket-bot/polymarket-copy-bot/.env

# Restart and verify
sudo systemctl restart polymarket-bot
sudo scripts/health_monitor.sh production comprehensive
```

### Backup Verification

```bash
# Verify backup integrity
sha256sum -c /path/to/backup.tar.gz.sha256

# Test backup extraction
tar -tzf /path/to/backup.tar.gz | head -10

# Verify encryption
gpg --verify /path/to/backup.tar.gz.gpg
```

## Troubleshooting

### Common Issues and Solutions

#### Service Won't Start

**Symptoms**: `systemctl status polymarket-bot` shows failed state

**Troubleshooting**:
```bash
# Check service logs
sudo journalctl -u polymarket-bot -n 50

# Check application logs
sudo tail -50 /home/polymarket-bot/polymarket-copy-bot/logs/*.log

# Verify permissions
ls -la /home/polymarket-bot/polymarket-copy-bot/main.py

# Check Python environment
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/venv/bin/python --version
```

**Resolution**:
```bash
# Fix permissions
sudo chmod 750 /home/polymarket-bot/polymarket-copy-bot/main.py
sudo chown polymarket-bot:polymarket-bot /home/polymarket-bot/polymarket-copy-bot/main.py

# Restart service
sudo systemctl restart polymarket-bot
```

#### High Memory Usage

**Symptoms**: Memory usage > 80%

**Troubleshooting**:
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10

# Check for memory leaks
sudo journalctl -u polymarket-bot | grep -i "memory\|leak"
```

**Resolution**:
```bash
# Restart service
sudo systemctl restart polymarket-bot

# Monitor memory usage
watch -n 30 'free -h'
```

#### Database Corruption

**Symptoms**: SQLite errors in logs

**Troubleshooting**:
```bash
# Check database integrity
sudo -u polymarket-bot sqlite3 /home/polymarket-bot/polymarket-copy-bot/data/trade_history.db "PRAGMA integrity_check;"

# Check database size
ls -lh /home/polymarket-bot/polymarket-copy-bot/data/trade_history.db
```

**Resolution**:
```bash
# Restore from backup
sudo scripts/recovery_secure.sh production data /path/to/latest_backup.tar.gz

# Rebuild database if needed
sudo -u polymarket-bot sqlite3 /home/polymarket-bot/polymarket-copy-bot/data/trade_history.db "VACUUM;"
```

#### Network Connectivity Issues

**Symptoms**: RPC connection failures

**Troubleshooting**:
```bash
# Test connectivity
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  https://polygon-rpc.com/

# Check DNS resolution
nslookup polygon-rpc.com

# Monitor network connections
netstat -t | grep :443 | wc -l
```

**Resolution**:
```bash
# Switch RPC endpoint in configuration
sudo nano /home/polymarket-bot/polymarket-copy-bot/.env

# Restart service
sudo systemctl restart polymarket-bot
```

### Diagnostic Commands

```bash
# System diagnostics
uptime && free -h && df -h && ps aux | grep polymarket

# Network diagnostics
ping -c 3 8.8.8.8 && traceroute -n polygon-rpc.com

# Application diagnostics
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/venv/bin/python -c "
import sys
sys.path.insert(0, '/home/polymarket-bot/polymarket-copy-bot')
from config.settings import settings
print('Config loaded successfully')
"

# Log analysis
grep -r "ERROR\|CRITICAL" /home/polymarket-bot/polymarket-copy-bot/logs/
```

## Maintenance Checklist

### Daily Checklist

- [ ] **Health Checks**: Run comprehensive health monitoring
- [ ] **Log Review**: Check for error patterns in logs
- [ ] **Resource Monitoring**: Verify CPU, memory, disk usage
- [ ] **Backup Verification**: Confirm backups completed successfully
- [ ] **Security Scan**: Quick security vulnerability check

### Weekly Checklist

- [ ] **System Updates**: Apply security patches (staging first)
- [ ] **Dependency Updates**: Update Python packages
- [ ] **Database Maintenance**: Vacuum and integrity checks
- [ ] **Log Rotation**: Verify log rotation is working
- [ ] **Backup Testing**: Test backup restoration
- [ ] **Performance Review**: Analyze system performance trends

### Monthly Checklist

- [ ] **Full System Audit**: Complete security and performance audit
- [ ] **Backup Strategy Review**: Evaluate backup retention and procedures
- [ ] **Documentation Update**: Update runbook with new procedures
- [ ] **Training Review**: Ensure team is trained on new procedures
- [ ] **Compliance Check**: Verify regulatory compliance

### Quarterly Checklist

- [ ] **Disaster Recovery Test**: Full disaster recovery simulation
- [ ] **Business Continuity**: Review and update BC procedures
- [ ] **Vendor Updates**: Evaluate new versions and security updates
- [ ] **Process Improvements**: Implement lessons learned
- [ ] **Resource Planning**: Plan for scaling and capacity needs

### Emergency Contacts Summary

- **Primary On-Call**: System Administrator (24/7) - +1 (555) 123-4567
- **DevOps Lead**: Business Hours - devops@company.com
- **Development Lead**: Business Hours - devlead@company.com
- **Management**: CTO - cto@company.com
- **Emergency Email**: emergency@company.com

---

**Version**: 1.0.0
**Last Updated**: December 25, 2025
**Review Date**: January 25, 2026
**Document Owner**: DevOps Team
