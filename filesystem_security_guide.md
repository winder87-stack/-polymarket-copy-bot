# Filesystem Security Guide for Polymarket Copy Bot

## Overview

This guide provides comprehensive filesystem security implementation for the Polymarket Copy Bot, including directory structure, permission management, security hardening, and backup/recovery procedures.

## Table of Contents

1. [Security Architecture](#security-architecture)
2. [Directory Structure](#directory-structure)
3. [Permission Management](#permission-management)
4. [Security Hardening](#security-hardening)
5. [Backup & Recovery](#backup--recovery)
6. [Monitoring & Auditing](#monitoring--auditing)
7. [Quick Setup](#quick-setup)
8. [Troubleshooting](#troubleshooting)
9. [Security Checklist](#security-checklist)

## Security Architecture

### Defense in Depth Strategy

The filesystem security implements multiple layers of protection:

```
┌─────────────────┐
│ User Isolation  │ ← Dedicated system users
├─────────────────┤
│ Permission Model│ ← Least privilege access
├─────────────────┤
│ File Encryption │ ← Sensitive data protection
├─────────────────┤
│ Integrity Checks│ ← Tamper detection
├─────────────────┤
│ Audit Logging   │ ← Access monitoring
└─────────────────┘
```

### Threat Model

**Threats Addressed:**
- Unauthorized access to private keys
- Trade data manipulation
- Configuration tampering
- Log file poisoning
- Backup data theft

**Security Controls:**
- File permission restrictions
- User/group isolation
- Encryption for sensitive data
- Integrity monitoring
- Comprehensive auditing

## Directory Structure

### Secure Directory Hierarchy

```
/home/polymarket-bot/polymarket-copy-bot/
├── main.py                           # 750 - BOT_USER:BOT_GROUP
├── main_staging.py                   # 750 - BOT_USER:BOT_GROUP
├── config/                           # 750 - BOT_USER:BOT_GROUP
│   ├── settings.py                   # 640 - BOT_USER:BOT_GROUP
│   ├── wallets.json                  # 600 - BOT_USER:BOT_GROUP
│   └── backup/                       # 700 - BOT_USER:BOT_GROUP
├── core/                             # 755 - BOT_USER:BOT_GROUP
├── utils/                            # 755 - BOT_USER:BOT_GROUP
├── scripts/                          # 755 - BOT_USER:BOT_GROUP
├── logs/                             # 750 - BOT_USER:BOT_GROUP
│   ├── trade_*.log                   # 640 - BOT_USER:BOT_GROUP
│   ├── environment_manager.log       # 640 - BOT_USER:BOT_GROUP
│   └── security_monitor_*.log        # 600 - BOT_USER:BOT_GROUP
├── data/                             # 750 - BOT_USER:BOT_GROUP
│   ├── trade_history/                # 700 - BOT_USER:BOT_GROUP
│   │   ├── trades_*.json             # 600 - BOT_USER:BOT_GROUP
│   │   └── encrypted/                # 700 - BOT_USER:BOT_GROUP (if encrypted)
│   ├── cache/                        # 755 - BOT_USER:BOT_GROUP
│   └── temp/                         # 755 - BOT_USER:BOT_GROUP
├── security/                         # 700 - BOT_USER:BOT_GROUP
│   ├── integrity/                    # 700 - BOT_USER:BOT_GROUP
│   │   └── file_hashes.db            # 600 - BOT_USER:BOT_GROUP
│   └── audit/                        # 700 - BOT_USER:BOT_GROUP
│       └── filesystem_audit.log      # 600 - BOT_USER:BOT_GROUP
├── backups/                          # 700 - BOT_USER:BOT_GROUP
│   ├── config/                       # 700 - BOT_USER:BOT_GROUP
│   │   └── config_*.tar.gz           # 600 - BOT_USER:BOT_GROUP
│   ├── data/                         # 700 - BOT_USER:BOT_GROUP
│   │   └── trade_data_*.tar.gz       # 600 - BOT_USER:BOT_GROUP
│   └── full/                         # 700 - BOT_USER:BOT_GROUP
│       └── full_backup_*.tar.gz      # 600 - BOT_USER:BOT_GROUP
├── venv/                             # 755 - BOT_USER:BOT_GROUP
├── .env                              # 600 - BOT_USER:BOT_GROUP
├── .env.staging                      # 600 - BOT_USER:BOT_GROUP
├── .env.development                  # 600 - BOT_USER:BOT_GROUP
├── requirements.txt                  # 640 - BOT_USER:BOT_GROUP
├── pyproject.toml                    # 640 - BOT_USER:BOT_GROUP
└── README.md                         # 644 - BOT_USER:BOT_GROUP
```

### Directory Creation Commands

```bash
# Create secure directory structure
sudo mkdir -p /home/polymarket-bot/polymarket-copy-bot/{logs,data/trade_history,data/cache,data/temp,security/{integrity,audit},backups/{config,data,full}}

# Set ownership
sudo chown -R polymarket-bot:polymarket-bot /home/polymarket-bot/polymarket-copy-bot

# Set directory permissions
sudo chmod 750 /home/polymarket-bot/polymarket-copy-bot/{logs,data}
sudo chmod 700 /home/polymarket-bot/polymarket-copy-bot/{data/trade_history,security,backups}
sudo chmod 700 /home/polymarket-bot/polymarket-copy-bot/backups/{config,data,full}
sudo chmod 700 /home/polymarket-bot/polymarket-copy-bot/security/{integrity,audit}
sudo chmod 755 /home/polymarket-bot/polymarket-copy-bot/{core,utils,scripts,data/cache,data/temp,venv}
```

## Permission Management

### File Permission Matrix

| File Type | Permission | Owner | Group | Description |
|-----------|------------|-------|-------|-------------|
| Private Keys | 600 | bot_user | bot_group | No access except owner |
| Configuration | 640 | bot_user | bot_group | Owner read/write, group read |
| Executables | 750 | bot_user | bot_group | Owner execute, group execute |
| Logs | 640 | bot_user | bot_group | Owner read/write, group read |
| Trade Data | 600 | bot_user | bot_group | No access except owner |
| Directories | 750/700 | bot_user | bot_group | Secure directory access |

### Permission Setting Commands

```bash
# Critical security files - owner only
sudo chmod 600 /home/polymarket-bot/polymarket-copy-bot/.env*
sudo chmod 600 /home/polymarket-bot/polymarket-copy-bot/config/wallets.json
sudo chmod 600 /home/polymarket-bot/polymarket-copy-bot/security/integrity/file_hashes.db
sudo chmod 600 /home/polymarket-bot/polymarket-copy-bot/security/audit/filesystem_audit.log

# Configuration files - owner read/write, group read
sudo chmod 640 /home/polymarket-bot/polymarket-copy-bot/config/settings.py
sudo chmod 640 /home/polymarket-bot/polymarket-copy-bot/requirements.txt
sudo chmod 640 /home/polymarket-bot/polymarket-copy-bot/pyproject.toml

# Executable files - owner execute, group execute
sudo chmod 750 /home/polymarket-bot/polymarket-copy-bot/main.py
sudo chmod 750 /home/polymarket-bot/polymarket-copy-bot/main_staging.py
sudo chmod 750 /home/polymarket-bot/polymarket-copy-bot/scripts/*.sh

# Log files - owner read/write, group read
sudo chmod 640 /home/polymarket-bot/polymarket-copy-bot/logs/*.log

# Trade data - owner only
sudo chmod 600 /home/polymarket-bot/polymarket-copy-bot/data/trade_history/*.json
```

### Permission Validation Script

```bash
#!/bin/bash
# validate_permissions.sh - Verify filesystem permissions

PROJECT_DIR="/home/polymarket-bot/polymarket-copy-bot"
ISSUES=0

echo "🔍 Validating filesystem permissions..."

# Check critical file permissions
check_permission() {
    local file="$1"
    local expected="$2"
    local description="$3"

    if [ -f "$file" ]; then
        local actual=$(stat -c "%a" "$file")
        if [ "$actual" != "$expected" ]; then
            echo "❌ $description: $file ($actual ≠ $expected)"
            ((ISSUES++))
        else
            echo "✅ $description: $file"
        fi
    fi
}

# Validate critical permissions
check_permission "$PROJECT_DIR/.env" "600" "Environment file"
check_permission "$PROJECT_DIR/config/wallets.json" "600" "Wallets config"
check_permission "$PROJECT_DIR/main.py" "750" "Main executable"
check_permission "$PROJECT_DIR/logs/*.log" "640" "Log files"

# Check for world-accessible files
WORLD_ACCESS=$(find "$PROJECT_DIR" -type f -perm -o+rwx 2>/dev/null)
if [ -n "$WORLD_ACCESS" ]; then
    echo "❌ World-accessible files found:"
    echo "$WORLD_ACCESS"
    ((ISSUES++))
fi

if [ $ISSUES -eq 0 ]; then
    echo "🎉 All permissions validated successfully!"
else
    echo "❌ Found $ISSUES permission issues"
    exit 1
fi
```

## Security Hardening

### User Isolation

```bash
# Create dedicated users
sudo useradd --system --gid polymarket --shell /bin/bash --home-dir /home/polymarket-bot --create-home polymarket-bot
sudo useradd --system --gid polymarket-staging --shell /bin/bash --home-dir /home/polymarket-staging --create-home polymarket-staging

# Set locked passwords (no login)
sudo passwd -l polymarket-bot
sudo passwd -l polymarket-staging

# Add to necessary groups
sudo usermod -aG systemd-journal polymarket-bot
sudo usermod -aG systemd-journal polymarket-staging
```

### Access Control Lists (ACLs)

```bash
# Install ACL support
sudo apt-get update && sudo apt-get install -y acl

# Allow monitoring user to read logs (if exists)
sudo setfacl -m u:monitoring:rx /home/polymarket-bot/polymarket-copy-bot/logs/

# Set ACL for backup access (if needed)
sudo setfacl -m u:backup:rx /home/polymarket-bot/polymarket-copy-bot/backups/
```

### File Integrity Monitoring

```bash
# Create integrity database
sudo -u polymarket-bot mkdir -p /home/polymarket-bot/polymarket-copy-bot/security/integrity
sudo -u polymarket-bot touch /home/polymarket-bot/polymarket-copy-bot/security/integrity/file_hashes.db
sudo chmod 600 /home/polymarket-bot/polymarket-copy-bot/security/integrity/file_hashes.db

# Calculate initial hashes
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
echo 'main.py:'\$(sha256sum main.py | awk '{print \$1}'):$(date +%s)' >> security/integrity/file_hashes.db
echo 'config/settings.py:'\$(sha256sum config/settings.py | awk '{print \$1}'):$(date +%s)' >> security/integrity/file_hashes.db
echo 'config/wallets.json:'\$(sha256sum config/wallets.json | awk '{print \$1}'):$(date +%s)' >> security/integrity/file_hashes.db
"
```

### Audit Logging Setup

```bash
# Install audit tools
sudo apt-get install -y auditd audispd-plugins

# Configure audit rules for sensitive files
sudo auditctl -w /home/polymarket-bot/polymarket-copy-bot/.env -p rwxa -k polymarket_env
sudo auditctl -w /home/polymarket-bot/polymarket-copy-bot/config/wallets.json -p rwxa -k polymarket_wallets
sudo auditctl -w /home/polymarket-bot/polymarket-copy-bot/data/trade_history -p rwxa -k polymarket_trades

# Make rules persistent
echo "-w /home/polymarket-bot/polymarket-copy-bot/.env -p rwxa -k polymarket_env" | sudo tee -a /etc/audit/rules.d/polymarket.rules
echo "-w /home/polymarket-bot/polymarket-copy-bot/config/wallets.json -p rwxa -k polymarket_wallets" | sudo tee -a /etc/audit/rules.d/polymarket.rules
echo "-w /home/polymarket-bot/polymarket-copy-bot/data/trade_history -p rwxa -k polymarket_trades" | sudo tee -a /etc/audit/rules.d/polymarket.rules

# Reload audit rules
sudo systemctl restart auditd
```

### Encryption Setup

```bash
# Install encryption tools
sudo apt-get install -y ecryptfs-utils gnupg

# Setup encrypted trade history directory (optional)
sudo -u polymarket-bot ecryptfs-setup-private
# Follow prompts to setup encrypted directory

# For production, consider full disk encryption or encrypted backups
```

## Backup & Recovery

### Automated Backup System

```bash
# Setup cron jobs for automated backups
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "# Polymarket backups"; } | crontab -u polymarket-bot -
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "0 2 * * * /home/polymarket-bot/polymarket-copy-bot/scripts/backup_secure.sh production all"; } | crontab -u polymarket-bot -
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "0 6 * * * /home/polymarket-bot/polymarket-copy-bot/scripts/backup_secure.sh production config"; } | crontab -u polymarket-bot -

# Staging backups (more frequent)
sudo crontab -u polymarket-staging -l 2>/dev/null | { cat; echo "# Polymarket staging backups"; } | crontab -u polymarket-staging -
sudo crontab -u polymarket-staging -l 2>/dev/null | { cat; echo "0 */4 * * * /home/polymarket-staging/polymarket-copy-bot/scripts/backup_secure.sh staging all"; } | crontab -u polymarket-staging -
```

### Backup Commands

```bash
# Configuration backup
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/backup_secure.sh production config

# Trade data backup
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/backup_secure.sh production data

# Full backup
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/backup_secure.sh production all
```

### Recovery Procedures

```bash
# List available backups
sudo /home/polymarket-bot/polymarket-copy-bot/scripts/recovery_secure.sh list production

# Recover configurations
sudo /home/polymarket-bot/polymarket-copy-bot/scripts/recovery_secure.sh production config /path/to/config_backup.tar.gz

# Recover trade data
sudo /home/polymarket-bot/polymarket-copy-bot/scripts/recovery_secure.sh production data /path/to/trade_data_backup.tar.gz

# Full recovery
sudo /home/polymarket-bot/polymarket-copy-bot/scripts/recovery_secure.sh production all /path/to/full_backup.tar.gz
```

### Backup Verification

```bash
# Verify backup integrity
sha256sum -c /path/to/backup.tar.gz.sha256

# Test backup extraction
tar -tzf /path/to/backup.tar.gz | head -10

# Verify encrypted backups
gpg --verify /path/to/backup.tar.gz.gpg
```

## Monitoring & Auditing

### Security Monitoring

```bash
# Run security monitoring
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/security_monitor.sh production

# Setup automated monitoring
sudo crontab -u polymarket-bot -l 2>/dev/null | { cat; echo "*/30 * * * * /home/polymarket-bot/polymarket-copy-bot/scripts/security_monitor.sh production"; } | crontab -u polymarket-bot -
```

### Audit Log Analysis

```bash
# View audit logs
sudo ausearch -k polymarket_env -i
sudo ausearch -k polymarket_wallets -i
sudo ausearch -k polymarket_trades -i

# Search for suspicious activity
sudo aureport --failed

# Generate audit reports
sudo aureport --summary
```

### Log Rotation Setup

```bash
# Configure logrotate for bot logs
sudo tee /etc/logrotate.d/polymarket-bot << EOF
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

# Apply logrotate configuration
sudo logrotate -f /etc/logrotate.d/polymarket-bot
```

## Quick Setup

### One-Command Security Setup

```bash
# Production environment
sudo /home/polymarket-bot/polymarket-copy-bot/scripts/filesystem_security.sh production

# Staging environment
sudo /home/polymarket-staging/polymarket-copy-bot/scripts/filesystem_security.sh staging

# Development environment
/home/user/polymarket-copy-bot/scripts/filesystem_security.sh development
```

### Validation Commands

```bash
# Validate security setup
sudo /home/polymarket-bot/polymarket-copy-bot/scripts/filesystem_security.sh production validate

# Run security monitoring
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/security_monitor.sh production

# Check permissions
sudo /home/polymarket-bot/polymarket-copy-bot/scripts/validate_permissions.sh
```

## Troubleshooting

### Common Issues

#### Permission Denied Errors

```bash
# Fix ownership
sudo chown -R polymarket-bot:polymarket-bot /home/polymarket-bot/polymarket-copy-bot

# Fix permissions
sudo chmod 600 /home/polymarket-bot/polymarket-copy-bot/.env
sudo chmod 640 /home/polymarket-bot/polymarket-copy-bot/config/settings.py
sudo chmod 750 /home/polymarket-bot/polymarket-copy-bot/main.py
```

#### Service Won't Start

```bash
# Check service status
sudo systemctl status polymarket-bot

# Check permissions on executable
ls -la /home/polymarket-bot/polymarket-copy-bot/main.py

# Check environment file permissions
ls -la /home/polymarket-bot/polymarket-copy-bot/.env

# Fix permissions
sudo chmod 750 /home/polymarket-bot/polymarket-copy-bot/main.py
sudo chmod 600 /home/polymarket-bot/polymarket-copy-bot/.env
```

#### Backup Failures

```bash
# Check available space
df -h /home/polymarket-bot/polymarket-copy-bot/backups

# Check backup script permissions
ls -la /home/polymarket-bot/polymarket-copy-bot/scripts/backup_secure.sh

# Run backup manually
sudo -u polymarket-bot /home/polymarket-bot/polymarket-copy-bot/scripts/backup_secure.sh production config
```

#### Integrity Check Failures

```bash
# Recalculate integrity hashes
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
rm security/integrity/file_hashes.db
touch security/integrity/file_hashes.db
echo 'main.py:'\$(sha256sum main.py | awk '{print \$1}'):$(date +%s)' >> security/integrity/file_hashes.db
"
```

### Emergency Recovery

```bash
# Stop all services
sudo systemctl stop polymarket-bot polymarket-bot-staging

# Emergency permission reset
sudo chown -R polymarket-bot:polymarket-bot /home/polymarket-bot/polymarket-copy-bot
sudo chmod -R go-rwx /home/polymarket-bot/polymarket-copy-bot
sudo chmod -R u+rwX /home/polymarket-bot/polymarket-copy-bot

# Reapply security
sudo /home/polymarket-bot/polymarket-copy-bot/scripts/filesystem_security.sh production

# Restart services
sudo systemctl start polymarket-bot
```

## Security Checklist

### Pre-Deployment Checklist

- [ ] Dedicated system users created
- [ ] File permissions set correctly (600 for secrets, 640 for configs)
- [ ] Directory permissions configured (750 for general, 700 for sensitive)
- [ ] File integrity monitoring enabled
- [ ] Audit logging configured
- [ ] Automated backups scheduled
- [ ] Log rotation configured
- [ ] Service runs with restricted privileges

### Ongoing Security Maintenance

- [ ] Regular permission audits
- [ ] Integrity check monitoring
- [ ] Backup integrity verification
- [ ] Log review and analysis
- [ ] Security updates applied
- [ ] Access pattern monitoring

### Incident Response

- [ ] Automated alerts for security violations
- [ ] Backup restoration procedures tested
- [ ] Service isolation maintained
- [ ] Forensic logging enabled
- [ ] Recovery procedures documented

### Performance Impact

The security measures have minimal performance impact:

- File permission checks: Negligible
- Integrity monitoring: <1% CPU during checks
- Audit logging: Minimal I/O overhead
- Encryption: Depends on data size (GPG ~10-20% overhead)

---

**Version**: 1.0.0
**Last Updated**: December 25, 2025
**Security Classification**: High
**Compliance**: Enterprise-grade filesystem security
