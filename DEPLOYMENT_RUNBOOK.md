# 🚀 Polymarket Copy Trading Bot - Deployment Runbook

## Executive Summary

This runbook provides comprehensive procedures for deploying, maintaining, and troubleshooting the Polymarket Copy Trading Bot in production environments. It includes step-by-step deployment procedures, rollback strategies, emergency contacts, and incident response protocols.

**Production Requirements:**
- ✅ All staging validation completed (7-day testing)
- ✅ All critical security issues resolved
- ✅ All performance benchmarks met
- ✅ Emergency contacts configured
- ✅ Rollback procedures tested

---

## 📋 Pre-Deployment Checklist

### [ ] System Prerequisites
- [ ] Ubuntu 24.04 LTS server provisioned
- [ ] Minimum 2GB RAM, 20GB storage available
- [ ] Root/sudo access configured
- [ ] Network connectivity to Polygon mainnet RPC
- [ ] SSH access configured for deployment user
- [ ] Backup storage configured

### [ ] Application Prerequisites
- [ ] Code deployed to main branch
- [ ] All CI/CD checks passed (security, performance, tests)
- [ ] Staging validation completed (7-day testing)
- [ ] Production configuration prepared
- [ ] Wallet funded with sufficient USDC
- [ ] Telegram alerts configured and tested

### [ ] Security Prerequisites
- [ ] Private keys secured (not in repository)
- [ ] Environment variables configured securely
- [ ] File permissions hardened
- [ ] Firewall rules configured
- [ ] Security monitoring enabled

### [ ] Operational Prerequisites
- [ ] Monitoring system configured
- [ ] Alert channels tested
- [ ] Backup procedures tested
- [ ] Rollback procedures documented
- [ ] Emergency contacts notified

---

## 🎯 Deployment Environments

### Staging Environment
- **Purpose**: Pre-production validation and testing
- **Network**: Polygon Mumbai testnet
- **Risk Level**: Low (testnet funds only)
- **Monitoring**: Full monitoring enabled
- **Duration**: 7-day validation period required

### Production Environment
- **Purpose**: Live trading with real funds
- **Network**: Polygon mainnet
- **Risk Level**: High (real financial risk)
- **Monitoring**: Full monitoring + additional safeguards
- **Requirements**: Staging validation completed

---

## 📦 Deployment Procedures

### Phase 1: Infrastructure Setup

#### 1.1 Server Provisioning
```bash
# Provision Ubuntu 24.04 server with:
# - 2GB RAM minimum
# - 20GB SSD storage
# - Public IP for monitoring access
# - Security groups configured (SSH only)

# Update system
sudo apt update && sudo apt upgrade -y

# Configure timezone
sudo timedatectl set-timezone UTC

# Configure firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80/tcp  # For health checks (optional)
```

#### 1.2 User and Security Setup
```bash
# Create deployment user (non-root)
sudo adduser polymarket-bot --disabled-password --gecos "Polymarket Bot"

# Configure SSH access
sudo mkdir -p /home/polymarket-bot/.ssh
sudo cp ~/.ssh/authorized_keys /home/polymarket-bot/.ssh/
sudo chown -R polymarket-bot:polymarket-bot /home/polymarket-bot/.ssh
sudo chmod 700 /home/polymarket-bot/.ssh
sudo chmod 600 /home/polymarket-bot/.ssh/authorized_keys

# Add to sudo group for deployment
sudo usermod -aG sudo polymarket-bot

# Configure passwordless sudo for deployment scripts
echo 'polymarket-bot ALL=(ALL) NOPASSWD: /home/polymarket-bot/polymarket-copy-bot/scripts/setup_ubuntu.sh' | sudo tee /etc/sudoers.d/polymarket-bot
echo 'polymarket-bot ALL=(ALL) NOPASSWD: /home/polymarket-bot/polymarket-copy-bot/scripts/setup_monitoring.sh' | sudo tee -a /etc/sudoers.d/polymarket-bot
```

#### 1.3 Application Deployment
```bash
# Switch to deployment user
sudo -u polymarket-bot bash

# Clone repository
cd /home/polymarket-bot
git clone <repository-url> polymarket-copy-bot
cd polymarket-copy-bot

# Checkout production branch/tag
git checkout main  # or specific tag
git pull origin main

# Make scripts executable
chmod +x scripts/*.sh

# Run setup script
sudo ./scripts/setup_ubuntu.sh
```

### Phase 2: Configuration Setup

#### 2.1 Environment Configuration
```bash
# Create production environment file
cp .env.template .env

# Edit with production values (NEVER commit to repository)
nano .env

# Required production configuration:
PRIVATE_KEY=0x...  # Production wallet private key
POLYGON_RPC_URL=https://polygon-rpc.com  # Mainnet RPC
CLOB_HOST=https://clob.polymarket.com
TELEGRAM_BOT_TOKEN=...  # Production alert bot
TELEGRAM_CHAT_ID=...    # Production alert channel
MAX_POSITION_SIZE=50.0  # Conservative for production
MAX_DAILY_LOSS=100.0    # Conservative for production
```

#### 2.2 Wallet Configuration
```bash
# Configure target wallets for copying
nano config/wallets.json

# Production wallet configuration:
{
  "target_wallets": [
    "0x...",  // Verified profitable traders
    "0x...",  // Additional traders
  ],
  "min_confidence_score": 0.7,
  "max_trade_frequency": 10,
  "min_trade_interval_minutes": 5
}
```

#### 2.3 Security Hardening
```bash
# Secure environment file
sudo chown root:root .env
sudo chmod 600 .env

# Verify file permissions
ls -la .env config/wallets.json

# Expected output:
# -rw------- 1 root root .env
# -rw-r----- 1 polymarket-bot polymarket-bot config/wallets.json
```

### Phase 3: Service Activation

#### 3.1 Pre-Deployment Testing
```bash
# Switch to application user
sudo -u polymarket-bot bash
cd /home/polymarket-bot/polymarket-copy-bot

# Activate virtual environment
source venv/bin/activate

# Validate configuration
python config/settings.py

# Test wallet connectivity
python -c "
from config.settings import settings
from web3 import Web3
w3 = Web3(Web3.HTTPProvider(settings.network.polygon_rpc_url))
print(f'Connected: {w3.is_connected()}')
print(f'Block: {w3.eth.block_number}')
print(f'Balance: {w3.eth.get_balance(settings.trading.wallet_address)}')
"

# Test alert system
python -c "
import asyncio
from utils.alerts import send_error_alert
asyncio.run(send_error_alert('🚀 Deployment test alert'))
"
```

#### 3.2 Service Startup
```bash
# Return to root/sudo
exit

# Enable and start service
sudo systemctl enable polymarket-bot
sudo systemctl start polymarket-bot

# Verify service status
sudo systemctl status polymarket-bot

# Check logs
sudo journalctl -u polymarket-bot -f -n 20

# Expected startup sequence:
# ✅ Settings loaded successfully
# 🚨 MAINNET ENVIRONMENT - REAL FUNDS AT RISK 🚨
# ✅ All critical settings validated successfully
# 🔄 Starting Polymarket Copy Trading Bot...
# 🎯 Detected X potential trades
```

### Phase 4: Post-Deployment Verification

#### 4.1 Functional Testing
```bash
# Monitor initial operation
sudo journalctl -u polymarket-bot -f

# Check wallet monitoring
# Should see: "🔍 Monitoring X wallets every 15 seconds"

# Check trade detection
# Should see: "🎯 Detected X potential trades"

# Verify alerts received in Telegram
# Should receive: "✅ **TRADE EXECUTED**" (if trades detected)
```

#### 4.2 Monitoring Setup
```bash
# Install monitoring system
sudo ./scripts/setup_monitoring.sh

# Enable monitoring
sudo systemctl enable polymarket-monitoring.timer
sudo systemctl start polymarket-monitoring.timer

# Run initial monitoring check
sudo -u polymarket-bot monitoring/monitor_all.py --verbose

# Verify monitoring dashboard
python monitoring/dashboard.py
```

#### 4.3 Health Checks
```bash
# Run health check script
python scripts/health_check.py

# Check monitoring status
./scripts/monitoring_status.sh

# Expected output:
# ✅ Service: RUNNING
# ✅ Security: PASSED
# ✅ Performance: GOOD
# ✅ Alerts: HEALTHY

# Run diagnostic check if issues found
python scripts/diagnostic_check.py --hours 1
```

---

## 🔄 Rollback Procedures

### Rollback Strategy Overview
- **Blue-Green Deployment**: Maintain previous version during deployment
- **Immediate Rollback**: < 5 minutes for critical issues
- **Gradual Rollback**: 30-60 minutes for non-critical issues
- **Data Preservation**: Trading history and configuration preserved

### Scenario 1: Code Issues (Immediate Rollback)

#### Detection
```
❌ CRITICAL ERROR in main.py line 123: Invalid API response
🚨 Alert: Service crashed with exit code 1
```

#### Rollback Steps
```bash
# 1. Stop current service
sudo systemctl stop polymarket-bot

# 2. Backup current state (if needed)
cp -r /home/polymarket-bot/polymarket-copy-bot /home/polymarket-bot/polymarket-copy-bot.backup.$(date +%Y%m%d_%H%M%S)

# 3. Rollback to previous version
cd /home/polymarket-bot/polymarket-copy-bot
git checkout HEAD~1  # Previous commit
git checkout .env    # Restore environment (if modified)

# 4. Reinstall dependencies (if changed)
source venv/bin/activate
pip install -r requirements.txt

# 5. Restart service
sudo systemctl start polymarket-bot

# 6. Verify rollback success
sudo systemctl status polymarket-bot
sudo journalctl -u polymarket-bot -f -n 10
```

#### Verification
- Service starts successfully
- No critical errors in logs
- Alert system sends "ROLLBACK COMPLETED" message
- Monitoring dashboard shows green status

### Scenario 2: Configuration Issues (Configuration Rollback)

#### Detection
```
⚠️ Configuration validation failed: INVALID_PRIVATE_KEY
🚨 Alert: Service failed to start - configuration error
```

#### Rollback Steps
```bash
# 1. Restore previous configuration
cp .env.backup .env

# 2. Validate configuration
sudo -u polymarket-bot bash -c "
cd /home/polymarket-bot/polymarket-copy-bot
source venv/bin/activate
python config/settings.py
"

# 3. Restart service
sudo systemctl restart polymarket-bot

# 4. Verify configuration
sudo journalctl -u polymarket-bot -f -n 5
```

### Scenario 3: Performance Issues (Gradual Rollback)

#### Detection
```
📊 PERFORMANCE REGRESSION: Trade latency increased by 300%
🚨 Alert: Performance degraded beyond threshold
```

#### Rollback Steps
```bash
# 1. Enable maintenance mode (stop trading)
sudo systemctl stop polymarket-bot

# 2. Switch to previous version
cd /home/polymarket-bot/polymarket-copy-bot
git checkout previous-stable-tag

# 3. Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# 4. Start service with reduced capacity
sudo systemctl start polymarket-bot

# 5. Monitor performance for 30 minutes
watch -n 30 './scripts/monitoring_status.sh'

# 6. Full rollback if performance not restored
# (Repeat steps 1-4 if needed)
```

### Scenario 4: Database/State Issues (Data Rollback)

#### Detection
```
💾 STATE CORRUPTION: Invalid trade history detected
🚨 Alert: Data integrity compromised
```

#### Rollback Steps
```bash
# 1. Stop service immediately
sudo systemctl stop polymarket-bot

# 2. Backup current state
cp -r data/ data.backup.emergency.$(date +%Y%m%d_%H%M%S)

# 3. Restore from backup
# Check available backups
ls -la data.backup.*

# Restore most recent good backup
cp -r data.backup.20241201_020000/* data/

# 4. Verify data integrity
python scripts/verify_data_integrity.py

# 5. Start service
sudo systemctl start polymarket-bot
```

---

## 📞 Emergency Contact List

### Primary Contacts (24/7 Response)

#### Development Team Lead
- **Name**: [Primary Developer Name]
- **Role**: Lead Developer
- **Phone**: [Direct Phone Number]
- **Email**: [Primary Email]
- **Telegram**: [@dev_lead_username]
- **Response SLA**: < 15 minutes for critical issues

#### Operations Lead
- **Name**: [Operations Lead Name]
- **Role**: DevOps Engineer
- **Phone**: [Direct Phone Number]
- **Email**: [Operations Email]
- **Telegram**: [@ops_lead_username]
- **Response SLA**: < 30 minutes for critical issues

#### Security Lead
- **Name**: [Security Lead Name]
- **Role**: Security Engineer
- **Phone**: [Direct Phone Number]
- **Email**: [Security Email]
- **Telegram**: [@security_lead_username]
- **Response SLA**: < 10 minutes for security incidents

### Secondary Contacts (Business Hours)

#### Product Manager
- **Name**: [Product Manager Name]
- **Email**: [Product Email]
- **Phone**: [Business Phone]
- **Availability**: Mon-Fri 9AM-6PM UTC

#### Legal/Compliance
- **Name**: [Legal Contact Name]
- **Email**: [Legal Email]
- **Phone**: [Legal Phone]
- **Availability**: Mon-Fri 9AM-5PM UTC

### External Contacts

#### Infrastructure Provider
- **Company**: [Hosting Provider]
- **Support**: [Support Phone/Email]
- **Emergency**: [Emergency Contact]
- **Data Center**: [Location]

#### Blockchain Infrastructure
- **Polygon Labs**: support@polygon.technology
- **Infura**: support@infura.io
- **Polymarket**: support@polymarket.com

---

## 🚨 Incident Response Procedures

**📋 Documentation:** Use `incident_response_template.md` for comprehensive incident documentation.

### Incident Classification

#### Severity 1 (Critical) - Immediate Action Required
**Impact**: System down, data loss, security breach, financial loss
**Response Time**: < 5 minutes
**Examples**:
- Service completely down
- Unauthorized access detected
- Large financial loss (> $1000)
- Data breach or exposure

#### Severity 2 (High) - Urgent Response Required
**Impact**: Degraded performance, partial system failure
**Response Time**: < 30 minutes
**Examples**:
- High error rates (> 50%)
- Performance degradation (> 50% slower)
- Alert system failure
- Single wallet monitoring failure

#### Severity 3 (Medium) - Response Within Hours
**Impact**: Minor issues, monitoring alerts
**Response Time**: < 4 hours
**Examples**:
- Occasional errors
- Slow performance
- Configuration warnings
- Monitoring alerts

#### Severity 4 (Low) - Routine Response
**Impact**: Minor operational issues
**Response Time**: Next business day
**Examples**:
- Log warnings
- Minor performance variations
- Non-critical monitoring alerts

### Incident Response Workflow

#### Phase 1: Detection and Assessment (0-5 minutes)
```bash
# 1. Acknowledge alert receipt
# Reply to alert: "INCIDENT ACKNOWLEDGED - Investigating"

# 2. Assess severity
./scripts/assess_incident_severity.sh

# 3. Notify incident response team
# Send message to incident channel with severity assessment

# 4. Gather initial information
INCIDENT_ID=$(date +%Y%m%d_%H%M%S)
mkdir -p incidents/$INCIDENT_ID

# Capture current state
sudo systemctl status polymarket-bot > incidents/$INCIDENT_ID/initial_status.txt
sudo journalctl -u polymarket-bot --since "1 hour ago" > incidents/$INCIDENT_ID/recent_logs.txt
./scripts/monitoring_status.sh > incidents/$INCIDENT_ID/monitoring_status.txt
```

#### Phase 2: Containment (5-30 minutes)
```bash
# 1. Implement immediate containment
case $SEVERITY in
    "CRITICAL")
        # Stop all trading immediately
        sudo systemctl stop polymarket-bot
        echo "CRITICAL: Trading stopped for safety"
        ;;
    "HIGH")
        # Reduce trading activity
        # Implement circuit breaker
        echo "HIGH: Reduced trading activity"
        ;;
    "MEDIUM"|"LOW")
        # Monitor closely, no immediate action
        echo "Monitoring incident closely"
        ;;
esac

# 2. Isolate affected components
# If specific wallet causing issues:
# Remove from target_wallets.json temporarily

# 3. Enable additional monitoring
# Increase log verbosity
# Enable debug logging if safe
```

#### Phase 3: Investigation (30-120 minutes)
```bash
# 1. Analyze logs and metrics
sudo journalctl -u polymarket-bot --since "24 hours ago" | grep -i error > incidents/$INCIDENT_ID/error_analysis.txt

# 2. Check system resources
htop -b -n 1 > incidents/$INCIDENT_ID/system_resources.txt

# 3. Run diagnostics
python scripts/diagnostic_check.py > incidents/$INCIDENT_ID/diagnostics.txt

# 4. Review recent changes
cd /home/polymarket-bot/polymarket-copy-bot
git log --oneline -10 > incidents/$INCIDENT_ID/recent_changes.txt

# 5. Check external dependencies
curl -f https://polygon-rpc.com > /dev/null && echo "RPC OK" || echo "RPC FAIL"
curl -f https://clob.polymarket.com/health > /dev/null && echo "CLOB OK" || echo "CLOB FAIL"
```

#### Phase 4: Resolution (2-24 hours)
```bash
# 1. Implement fix
case $INCIDENT_TYPE in
    "CODE_BUG")
        # Deploy hotfix
        git checkout fix-branch
        sudo systemctl restart polymarket-bot
        ;;
    "CONFIG_ERROR")
        # Fix configuration
        nano .env  # Apply fix
        sudo systemctl restart polymarket-bot
        ;;
    "RESOURCE_ISSUE")
        # Scale resources or optimize code
        # Implement the fix
        ;;
    "EXTERNAL_DEPENDENCY")
        # Wait for external fix or implement workaround
        # Switch RPC providers, etc.
        ;;
esac

# 2. Test fix
python scripts/health_check.py
./scripts/monitoring_status.sh

# 3. Gradual rollout
# Start with reduced capacity
# Monitor for 30 minutes
# Gradually increase capacity
```

#### Phase 5: Recovery and Prevention (1-7 days)
```bash
# 1. Full system recovery
sudo systemctl start polymarket-bot  # If stopped

# 2. Verify system stability
for i in {1..24}; do
    ./scripts/health_check.py
    sleep 3600  # Check hourly for 24 hours
done

# 3. Document incident
# Create incident report
cat > incidents/$INCIDENT_ID/incident_report.md << EOF
# Incident Report: $INCIDENT_ID

## Summary
[Brief description of incident]

## Timeline
- Detected: [timestamp]
- Resolved: [timestamp]
- Duration: [duration]

## Impact
[Description of impact]

## Root Cause
[Analysis of root cause]

## Resolution
[Steps taken to resolve]

## Prevention
[Measures to prevent recurrence]

## Lessons Learned
[Key takeaways]
EOF

# 4. Implement preventive measures
# Add monitoring alerts
# Update configurations
# Implement code fixes
# Update documentation
```

### Communication Procedures

#### Internal Communication
1. **Incident Channel**: All incident communication in dedicated Telegram/Slack channel
2. **Status Updates**: Every 30 minutes during active incident
3. **Escalation**: Immediate notification to appropriate team members
4. **Post-Mortem**: Detailed analysis shared with all stakeholders

#### External Communication
1. **Customer Impact**: Notify affected users if applicable
2. **Status Page**: Update external status page if available
3. **Transparency**: Provide regular updates on resolution progress
4. **Post-Incident**: Share summary of incident and resolution

---

## 📊 Monitoring and Alerting

### Key Metrics to Monitor

#### System Health
- Service uptime (> 99.9%)
- Memory usage (< 512MB)
- CPU usage (< 80%)
- Disk space (> 10% free)
- Network connectivity (100%)

#### Application Metrics
- Trade execution success rate (> 95%)
- Response time (< 5 seconds)
- Error rate (< 5%)
- Alert delivery success (> 95%)
- Wallet monitoring coverage (100%)

#### Business Metrics
- Daily P&L tracking
- Trade volume monitoring
- Risk limit compliance
- Position size monitoring

### Alert Escalation Matrix

| Alert Level | Initial Response | Escalation | Communication |
|-------------|------------------|------------|----------------|
| Critical | < 5 min | Immediate call | All contacts |
| High | < 30 min | Team lead | Incident channel |
| Medium | < 4 hours | On-call engineer | Monitoring channel |
| Low | Next day | Email | Log only |

---

## 🧪 Testing Procedures

### Pre-Deployment Testing
```bash
# 1. Unit tests
pytest tests/unit/ -v --cov=. --cov-report=term-missing

# 2. Integration tests
pytest tests/integration/ -v

# 3. Performance tests
python monitoring/performance_benchmark.py

# 4. Security tests
python monitoring/security_scanner.py

# 5. Configuration validation
python config/settings.py
```

### Post-Deployment Testing
```bash
# 1. Health checks
python scripts/health_check.py

# 2. Functional testing
# - Wallet monitoring active
# - Trade detection working
# - Alert system functional
# - Performance within bounds

# 3. Load testing (if applicable)
# Simulate high-frequency trading scenarios

# 4. Failover testing
# Test rollback procedures
```

---

## 📋 Maintenance Procedures

### Daily Maintenance
- [ ] Review monitoring dashboard
- [ ] Check system resource usage
- [ ] Verify backup integrity
- [ ] Review security scan results
- [ ] Check alert delivery

### Weekly Maintenance
- [ ] Update dependencies (security patches)
- [ ] Review and rotate logs
- [ ] Test backup restoration
- [ ] Update monitoring baselines
- [ ] Review incident reports

### Monthly Maintenance
- [ ] Full security audit
- [ ] Performance optimization review
- [ ] Disaster recovery testing
- [ ] Compliance review
- [ ] Documentation updates

---

## 🎯 Success Criteria

### Deployment Success
- ✅ Service starts within 5 minutes
- ✅ All health checks pass
- ✅ Alert system functional
- ✅ Monitoring systems active
- ✅ No critical errors in logs

### Operational Success
- ✅ 99.9% uptime maintained
- ✅ All performance benchmarks met
- ✅ Zero security incidents
- ✅ All alerts responded to within SLA
- ✅ Successful daily maintenance completion

### Business Success
- ✅ Trading objectives achieved
- ✅ Risk limits never exceeded
- ✅ Positive P&L maintained
- ✅ Stakeholder confidence high

---

## 📞 Quick Reference

### Emergency Commands
```bash
# Stop all trading immediately
sudo systemctl stop polymarket-bot

# Quick rollback to previous version
cd /home/polymarket-bot/polymarket-copy-bot && git checkout HEAD~1 && sudo systemctl restart polymarket-bot

# Assess incident severity
./scripts/assess_incident_severity.sh

# Emergency monitoring check
./scripts/monitoring_status.sh

# Send emergency alert
python -c "import asyncio; from utils.alerts import send_error_alert; asyncio.run(send_error_alert('🚨 EMERGENCY: Manual intervention required'))"
```

### Status Check Commands
```bash
# Overall system status
./scripts/monitoring_status.sh

# Comprehensive health check
python scripts/health_check.py --verbose

# Detailed diagnostics
python scripts/diagnostic_check.py --hours 1

# Service status
sudo systemctl status polymarket-bot

# Recent logs
sudo journalctl -u polymarket-bot -f -n 20

# Performance metrics
python monitoring/dashboard.py
```

### Contact Escalation
1. **Individual Issue**: Contact primary on-call engineer
2. **Service Down**: Contact operations lead immediately
3. **Security Breach**: Contact security lead immediately
4. **Financial Loss**: Contact development lead immediately

---

*This deployment runbook ensures safe, reliable, and efficient operation of the Polymarket Copy Trading Bot in production environments. Follow all procedures carefully and maintain detailed records of all deployments and incidents.*
