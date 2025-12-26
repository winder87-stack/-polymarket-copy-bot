# Production Deployment Plan for Polymarket Copy Trading Bot

## Executive Summary

This document outlines a comprehensive production deployment strategy for the Polymarket Copy Trading Bot on bare-metal Ubuntu 24.04 LTS servers. The deployment follows enterprise-grade practices with high availability, disaster recovery, and compliance monitoring.

## Architecture Overview

### Network Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           External Network                               │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                         Load Balancer (HAProxy)                     │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │                    Floating IP: 192.168.1.10                    │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  └─────────┬───────────────────────────────────────────────────────────┘ │
│            │                                                             │
│  ┌─────────┼─────────┐  ┌─────────────────────────────────────────────┐ │
│  │         │         │  │                Backup Storage                 │ │
│  │   ┌─────▼─────┐   │  │  ┌─────────────────────────────────────────┐ │ │
│  │   │ Primary   │   │  │  │         Offsite S3 Bucket               │ │ │
│  │   │ Server    │   │  │  │  s3://polymarket-backups/production/    │ │ │
│  │   │192.168.1.100│   │  │  └─────────────────────────────────────────┘ │ │
│  │   └─────────────┘   │  └─────────────────────────────────────────────┘ │
│  │                     │                                                  │
│  │   ┌─────────────┐   │  ┌─────────────────────────────────────────────┐ │
│  │   │ Standby     │   │  │           Local Backups                     │ │ │
│  │   │ Server      │   │  │  /var/backups/polymarket/                   │ │ │
│  │   │192.168.1.101│   │  │  └─────────────────────────────────────────┘ │ │
│  └─────────────────────┘  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Server Specifications

#### Primary Production Server
- **OS**: Ubuntu 24.04 LTS (bare-metal)
- **CPU**: 8-core Intel Xeon (3.0 GHz+)
- **RAM**: 32GB DDR4 ECC
- **Storage**: 500GB NVMe SSD (RAID 1)
- **Network**: 1Gbps dedicated connection
- **IP**: 192.168.1.100 (static)

#### Standby/Failover Server
- **OS**: Ubuntu 24.04 LTS (bare-metal)
- **CPU**: 8-core Intel Xeon (3.0 GHz+)
- **RAM**: 32GB DDR4 ECC
- **Storage**: 500GB NVMe SSD (RAID 1)
- **Network**: 1Gbps dedicated connection
- **IP**: 192.168.1.101 (static)

#### Load Balancer (Optional)
- **OS**: Ubuntu 24.04 LTS
- **CPU**: 4-core processor
- **RAM**: 8GB
- **Storage**: 100GB SSD
- **Software**: HAProxy

### Storage Requirements

| Component | Size | Retention | Backup |
|-----------|------|-----------|--------|
| Application Code | 500MB | N/A | Git |
| Configuration | 50MB | Forever | Versioned |
| Trade History | 10GB/month | 90 days | Encrypted |
| Logs | 5GB/month | 30 days | Compressed |
| Backups | 100GB | 30 days | Offsite |

## 1. Server Provisioning

### 1.1 Ubuntu 24.04 LTS Setup

**Terminal Commands:**
```bash
# Download Ubuntu 24.04 LTS ISO
wget https://releases.ubuntu.com/24.04/ubuntu-24.04-live-server-amd64.iso

# Create bootable USB (on separate machine)
sudo dd if=ubuntu-24.04-live-server-amd64.iso of=/dev/sdX bs=4M status=progress

# Boot from USB and follow installation wizard
# Select:
# - Language: English
# - Keyboard: English (US)
# - Network: DHCP (temporary)
# - Storage: Use entire disk with LVM
# - Profile: Minimal installation
# - SSH: Install OpenSSH server
# - Snap: Do not install
```

### 1.2 Network Configuration

**Primary Server (/etc/netplan/00-installer-config.yaml):**
```yaml
network:
  version: 2
  ethernets:
    enp1s0:
      addresses:
        - 192.168.1.100/24
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 1.1.1.1
```

**Standby Server (/etc/netplan/00-installer-config.yaml):**
```yaml
network:
  version: 2
  ethernets:
    enp1s0:
      addresses:
        - 192.168.1.101/24
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 1.1.1.1
```

**Apply network configuration:**
```bash
sudo netplan apply
sudo systemctl restart systemd-networkd
```

### 1.3 SSH Hardening

**Configuration (/etc/ssh/sshd_config):**
```bash
# SSH Server Configuration - Hardened for Production
Port 22
AddressFamily inet
ListenAddress 0.0.0.0

# Protocol and authentication
Protocol 2
PermitRootLogin no
StrictModes yes
MaxAuthTries 3
MaxSessions 5

# Password authentication
PasswordAuthentication no
PermitEmptyPasswords no
ChallengeResponseAuthentication no

# Public key authentication
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys

# GSSAPI options
GSSAPIAuthentication no
GSSAPICleanupCredentials no

# Kerberos options
KerberosAuthentication no

# Hostbased authentication
HostbasedAuthentication no
IgnoreUserKnownHosts yes
IgnoreRhosts yes

# Login restrictions
AllowUsers admin polymarket-bot
LoginGraceTime 30
PermitUserEnvironment no

# Connection settings
ClientAliveInterval 300
ClientAliveCountMax 2
TCPKeepAlive yes
UseDNS no

# Logging
LogLevel VERBOSE
SyslogFacility AUTH

# SFTP
Subsystem sftp /usr/lib/openssh/sftp-server -f AUTHPRIV -l INFO
```

### 1.4 Firewall Configuration (UFW)

**Setup commands:**
```bash
# Install UFW
sudo apt update && sudo apt install -y ufw

# Reset to defaults
sudo ufw --force reset

# Set default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (rate limited)
sudo ufw limit ssh

# Allow application ports
sudo ufw allow 80/tcp      # HTTP monitoring
sudo ufw allow 443/tcp     # HTTPS monitoring
sudo ufw allow 8080/tcp    # Web dashboard
sudo ufw allow 9090/tcp    # Prometheus metrics

# Enable firewall
echo "y" | sudo ufw enable

# Verify
sudo ufw status verbose
```

### 1.5 System Hardening

**Kernel parameters (/etc/sysctl.d/99-security.conf):**
```bash
# Network security
net.ipv4.ip_forward=0
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.default.accept_redirects=0
net.ipv4.conf.all.secure_redirects=0
net.ipv4.conf.default.secure_redirects=0
net.ipv4.conf.all.accept_source_route=0
net.ipv4.conf.default.accept_source_route=0
net.ipv4.conf.all.rp_filter=1
net.ipv4.conf.default.rp_filter=1
net.ipv4.icmp_echo_ignore_broadcasts=1
net.ipv4.icmp_ignore_bogus_error_responses=1
net.ipv4.tcp_syncookies=1
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1

# Kernel security
kernel.dmesg_restrict=1
kernel.kptr_restrict=2
kernel.sysrq=0
kernel.yama.ptrace_scope=1
kernel.core_uses_pid=1
kernel.randomize_va_space=2
kernel.panic=60
kernel.panic_on_oops=60

# Memory security
vm.mmap_min_addr=65536

# File system security
fs.suid_dumpable=0
fs.protected_hardlinks=1
fs.protected_symlinks=1
```

**Apply hardening:**
```bash
sudo sysctl -p /etc/sysctl.d/99-security.conf
```

## 2. Application Deployment

### 2.1 Directory Structure

**Create deployment directories:**
```bash
# Bot user and directories
sudo useradd -m -s /bin/bash -G sudo polymarket-bot
sudo mkdir -p /home/polymarket-bot/polymarket-copy-bot
sudo mkdir -p /etc/polymarket
sudo mkdir -p /var/log/polymarket
sudo mkdir -p /var/lib/polymarket
sudo mkdir -p /var/backups/polymarket

# Set ownership
sudo chown -R polymarket-bot:polymarket-bot /home/polymarket-bot
sudo chown -R polymarket-bot:polymarket-bot /var/log/polymarket
sudo chown -R polymarket-bot:polymarket-bot /var/lib/polymarket
sudo chown -R polymarket-bot:polymarket-bot /var/backups/polymarket

# Set permissions
sudo chmod 750 /home/polymarket-bot
sudo chmod 750 /etc/polymarket
sudo chmod 750 /var/log/polymarket
sudo chmod 750 /var/lib/polymarket
sudo chmod 700 /var/backups/polymarket
```

### 2.2 Secrets Management

**Environment file (/etc/polymarket/.env):**
```bash
# Polymarket API Configuration
POLYGON_RPC_URL=https://polygon-rpc.com
PRIVATE_KEY=your_private_key_here
WALLET_ADDRESS=0x...

# Application Configuration
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_POSITION_SIZE=1000
STOP_LOSS_PERCENTAGE=5

# Security Configuration
ENCRYPTION_KEY=your_strong_encryption_key_here
API_SECRET_KEY=your_api_secret_here

# Monitoring Configuration
HEALTH_CHECK_INTERVAL=30
METRICS_PORT=9090
DASHBOARD_PORT=8080
```

**Secure the environment file:**
```bash
sudo chmod 600 /etc/polymarket/.env
sudo chown polymarket-bot:polymarket-bot /etc/polymarket/.env
```

### 2.3 Deployment Script Execution

**Run deployment script:**
```bash
# Switch to bot user
sudo su - polymarket-bot

# Clone or copy application code
git clone https://github.com/your-org/polymarket-copy-bot.git
cd polymarket-copy-bot

# Run deployment script
./scripts/deploy_application.sh production rolling latest
```

### 2.4 Configuration Validation

**Validate configuration:**
```bash
# Test configuration loading
python3 -c "
from config.settings import settings
settings.validate_critical_settings()
print('Configuration validation successful')
"

# Test database connectivity
python3 -c "
import sqlite3
conn = sqlite3.connect('data/trade_history.db')
conn.close()
print('Database connectivity test passed')
"
```

## 3. High Availability Setup

### 3.1 SSH Key Configuration

**Generate and distribute SSH keys:**
```bash
# On primary server
sudo su - polymarket-bot
ssh-keygen -t rsa -b 4096 -f ~/.ssh/ha_rsa -N ""

# Copy public key to standby
ssh-copy-id -i ~/.ssh/ha_rsa.pub polymarket-bot@192.168.1.101

# On standby server
sudo su - polymarket-bot
ssh-copy-id -i ~/.ssh/ha_rsa.pub polymarket-bot@192.168.1.100
```

### 3.2 Rsync Configuration

**Setup rsync daemon (/etc/rsyncd.conf):**
```bash
# Polymarket HA Rsync Configuration
uid = polymarket-bot
gid = polymarket-bot
use chroot = yes
read only = no
list = no
auth users = polymarket_sync
secrets file = /etc/rsyncd.secrets
strict modes = yes

[polymarket_data]
    path = /home/polymarket-bot/polymarket-copy-bot/data
    comment = Polymarket trading data
    read only = no
    auth users = polymarket_sync
```

**Create rsync password:**
```bash
echo "polymarket_sync:CHANGE_THIS_PASSWORD_IMMEDIATELY" > /etc/rsyncd.secrets
chmod 600 /etc/rsyncd.secrets
```

### 3.3 Floating IP Management

**Create floating IP script (/usr/local/bin/manage_floating_ip.sh):**
```bash
#!/bin/bash
INTERFACE="enp1s0"
VIP="$1"
ACTION="$2"

case "$ACTION" in
    add)
        ip addr add "$VIP/24" dev "$INTERFACE"
        arping -c 3 -S "$VIP" "$VIP"
        ;;
    remove)
        ip addr del "$VIP/24" dev "$INTERFACE"
        ;;
    check)
        ip addr show "$INTERFACE" | grep -q "$VIP"
        ;;
esac
```

### 3.4 HAProxy Load Balancer

**Install and configure HAProxy:**
```bash
sudo apt install -y haproxy

# Configure HAProxy (/etc/haproxy/haproxy.cfg)
cat > /etc/haproxy/haproxy.cfg << 'EOF'
global
    log /dev/log local0
    log /dev/log local1 notice
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s
    user haproxy
    group haproxy
    daemon

defaults
    log global
    mode http
    option httplog
    option dontlognull
    timeout connect 5000
    timeout client 50000
    timeout server 50000

frontend polymarket_api
    bind 192.168.1.10:80
    bind 192.168.1.10:443 ssl crt /etc/ssl/certs/polymarket.pem
    default_backend polymarket_servers

backend polymarket_servers
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200
    server primary 192.168.1.100:8080 check
    server standby 192.168.1.101:8080 check backup
EOF

sudo systemctl enable haproxy
sudo systemctl start haproxy
```

### 3.5 Cron Jobs for Monitoring

**Setup monitoring cron jobs:**
```bash
# As polymarket-bot user
crontab -e

# Add these lines:
* * * * * /usr/local/bin/polymarket_heartbeat.sh
*/5 * * * * /usr/local/bin/polymarket_sync.sh incremental
0 2 * * * /usr/local/bin/polymarket_sync.sh full
```

## 4. Disaster Recovery

### 4.1 Backup Strategy

**Daily backup cron job:**
```bash
# Add to root crontab
0 2 * * * /home/polymarket-bot/polymarket-copy-bot/scripts/disaster_recovery.sh backup production full
```

**Backup verification:**
```bash
# Verify backup integrity
./scripts/disaster_recovery.sh verify production /var/backups/polymarket/app_production_$(date +%Y%m%d).tar.gz
```

### 4.2 Recovery Procedures

**Point-in-time recovery:**
```bash
# Stop services
sudo systemctl stop polymarket-bot

# Restore from backup
./scripts/disaster_recovery.sh restore production full 20241225_020000

# Verify recovery
./scripts/deploy_application.sh production test

# Restart services
sudo systemctl start polymarket-bot
```

### 4.3 Offsite Backup

**AWS S3 configuration:**
```bash
# Install AWS CLI
sudo apt install -y awscli

# Configure AWS credentials
aws configure

# Upload backup to S3
aws s3 cp /var/backups/polymarket/ s3://polymarket-backups/production/ --recursive --exclude "*" --include "*.tar.gz"
```

**Restore from S3:**
```bash
# Download from S3
aws s3 cp s3://polymarket-backups/production/ /var/backups/polymarket/ --recursive

# Restore locally
./scripts/disaster_recovery.sh restore production full <timestamp>
```

## 5. Compliance & Auditing

### 5.1 Audit Logging Setup

**Configure audit rules (/etc/audit/rules.d/polymarket.rules):**
```bash
# Polymarket specific audit rules
-w /home/polymarket-bot/ -p rwxa -k polymarket_files
-w /etc/polymarket/ -p rwxa -k polymarket_config

# Monitor network activity
-a always,exit -F arch=b64 -S socket -F a0=2 -k network_socket

# Monitor privilege escalation
-w /bin/su -p x -k privilege_escalation

# Monitor system calls
-a always,exit -F arch=b64 -S execve -k execute
```

### 5.2 Compliance Monitoring

**Daily compliance audit:**
```bash
# Add to cron (as root)
0 6 * * * /home/polymarket-bot/polymarket-copy-bot/scripts/compliance_audit.sh audit production comprehensive
```

**Compliance report generation:**
```bash
# Generate compliance report
./scripts/compliance_audit.sh report production
```

### 5.3 Data Retention Policy

**Log rotation configuration (/etc/logrotate.d/polymarket):**
```bash
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
```

**Data cleanup script:**
```bash
# Remove old trade data (>90 days)
find /home/polymarket-bot/polymarket-copy-bot/data/trade_history -name "*.json" -mtime +90 -delete

# Remove old logs (>30 days)
find /var/log/polymarket -name "*.log" -mtime +30 -delete
```

## Go-Live Checklist

### Pre-Deployment Checklist

- [ ] **Server Provisioning**
  - [ ] Ubuntu 24.04 LTS installed on both servers
  - [ ] Network configuration applied and tested
  - [ ] SSH hardened and key-based authentication configured
  - [ ] UFW firewall configured and active
  - [ ] System hardening applied (sysctl, PAM)
  - [ ] Administrative user created and configured

- [ ] **Security Configuration**
  - [ ] Bot user created with proper permissions
  - [ ] Directory structure created and secured
  - [ ] Environment variables configured and encrypted
  - [ ] Wallets configuration validated
  - [ ] SSL certificates installed (if using HTTPS)

- [ ] **Application Deployment**
  - [ ] Application code deployed successfully
  - [ ] Python virtual environment created
  - [ ] Dependencies installed and verified
  - [ ] Configuration validated
  - [ ] Service configured and enabled

- [ ] **High Availability**
  - [ ] SSH keys exchanged between servers
  - [ ] Rsync configured and tested
  - [ ] Floating IP scripts created
  - [ ] HAProxy installed and configured
  - [ ] Monitoring cron jobs configured

- [ ] **Monitoring & Alerting**
  - [ ] System monitoring configured
  - [ ] Application monitoring enabled
  - [ ] Alerting system configured
  - [ ] Log aggregation working
  - [ ] Dashboard accessible

### Deployment Day Checklist

- [ ] **Final Preparations**
  - [ ] All pre-deployment checks completed
  - [ ] Backup created before deployment
  - [ ] Rollback plan documented and tested
  - [ ] Emergency contacts confirmed
  - [ ] Monitoring alerts enabled

- [ ] **Go-Live Sequence**
  - [ ] Deploy to staging environment first
  - [ ] Validate staging deployment
  - [ ] Deploy to production standby server
  - [ ] Validate standby deployment
  - [ ] Switch floating IP to standby for testing
  - [ ] Deploy to production primary server
  - [ ] Validate primary deployment
  - [ ] Switch floating IP back to primary
  - [ ] Monitor for 1 hour post-deployment

- [ ] **Post-Deployment Validation**
  - [ ] Service health checks passing
  - [ ] Application responding to API calls
  - [ ] Trading functionality verified
  - [ ] Monitoring dashboards updated
  - [ ] Alert notifications working
  - [ ] Backup verification completed

### Emergency Contacts

| Role | Name | Phone | Email |
|------|------|-------|-------|
| Primary On-Call | System Administrator | +1-555-123-4567 | admin@company.com |
| DevOps Lead | DevOps Engineer | +1-555-123-4568 | devops@company.com |
| Application Owner | Product Manager | +1-555-123-4569 | product@company.com |
| Security Officer | Security Team | +1-555-123-4570 | security@company.com |

### Rollback Procedures

#### Immediate Rollback (< 15 minutes)
1. Switch floating IP to last known good server
2. Stop failed service: `systemctl stop polymarket-bot`
3. Restore from backup: `./scripts/disaster_recovery.sh restore production full <backup_timestamp>`
4. Restart service: `systemctl start polymarket-bot`
5. Validate service health

#### Full Environment Rollback (< 4 hours)
1. Stop all services on both servers
2. Restore complete environment from backup
3. Reconfigure HA and load balancing
4. Restart services and validate
5. Update monitoring and alerting

### Success Metrics

- **Service Availability**: 99.9% uptime
- **Recovery Time**: < 4 hours (RTO)
- **Data Loss**: < 15 minutes (RPO)
- **Compliance Score**: > 95%
- **Performance**: < 100ms average response time

### Monitoring Dashboards

Access URLs:
- **System Monitoring**: http://192.168.1.10:8080/system
- **Application Metrics**: http://192.168.1.10:8080/metrics
- **HA Status**: http://192.168.1.10:8080/ha
- **Compliance Reports**: http://192.168.1.10:8080/compliance

### Documentation Updates

Post-deployment documentation to update:
- Network diagrams with actual IP addresses
- Emergency contact list with current personnel
- Backup schedule with actual timings
- Monitoring alert thresholds
- Compliance reporting schedule

---

## Conclusion

This production deployment plan provides a comprehensive, enterprise-grade approach to deploying the Polymarket Copy Trading Bot. The plan emphasizes security, high availability, disaster recovery, and compliance throughout the entire lifecycle.

**Key Success Factors:**
- Thorough testing in staging environment
- Complete documentation and runbooks
- Automated monitoring and alerting
- Regular backup verification
- Continuous compliance monitoring

**Risk Mitigation:**
- Multiple rollback strategies
- Comprehensive backup and recovery procedures
- High availability with automatic failover
- Security hardening and compliance monitoring
- Regular testing and validation procedures

For questions or clarifications, contact the DevOps Lead or System Administrator.
