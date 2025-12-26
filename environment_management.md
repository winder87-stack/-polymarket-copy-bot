# Environment Management System for Polymarket Copy Bot

## Overview

This document provides comprehensive guidance for managing virtual environments, dependencies, and configurations for the Polymarket Copy Bot across different environments (production, staging, development).

## Table of Contents

1. [Quick Start](#quick-start)
2. [Environment Architecture](#environment-architecture)
3. [Environment Setup](#environment-setup)
4. [Environment Management](#environment-management)
5. [Dependency Management](#dependency-management)
6. [Environment Validation](#environment-validation)
7. [Health Monitoring](#health-monitoring)
8. [Environment Repair](#environment-repair)
9. [Multi-Environment Support](#multi-environment-support)
10. [Troubleshooting](#troubleshooting)
11. [Best Practices](#best-practices)

## Quick Start

### One-Command Setup

For a completely fresh setup:

```bash
# Production environment
sudo bash scripts/env_setup.sh production

# Staging environment (recommended first)
sudo bash scripts/env_setup.sh staging

# Development environment
bash scripts/env_setup.sh development
```

### Environment Activation

```bash
# Activate production
source scripts/env_activate.sh production

# Activate staging
source scripts/env_activate.sh staging

# Activate development
source scripts/env_activate.sh development
```

### Environment Validation

```bash
# Validate current environment
bash scripts/env_validate.sh

# Validate specific environment
bash scripts/env_validate.sh production
```

## Environment Architecture

### Directory Structure

```
/home/ink/polymarket-copy-bot/
├── venv/                                    # Production virtual environment
├── environments/
│   ├── staging/venv/                       # Staging virtual environment
│   └── development/venv/                   # Development virtual environment
├── requirements/                           # Environment-specific requirements
│   ├── requirements-production.txt
│   ├── requirements-staging.txt
│   └── requirements-development.txt
├── config/                                 # Configuration files
├── scripts/                                # Management scripts
├── utils/                                  # Python utilities
├── logs/                                   # Log files
├── data/                                   # Data files
└── backups/                               # Environment backups
```

### Environment Specifications

| Environment | Network | Virtual Env | Config File | Service Name |
|-------------|---------|-------------|-------------|--------------|
| production | Polygon Mainnet | `venv/` | `.env` | `polymarket-bot` |
| staging | Polygon Mumbai | `environments/staging/venv/` | `.env.staging` | `polymarket-bot-staging` |
| development | Polygon Amoy | `environments/development/venv/` | `.env.development` | N/A |

## Environment Setup

### Prerequisites

#### System Requirements
- Ubuntu 24.04 or compatible Linux distribution
- Python 3.9 - 3.11
- 4GB RAM minimum, 8GB recommended
- 10GB free disk space

#### System Dependencies
```bash
# Install system packages
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl build-essential
```

### Production Environment Setup

```bash
# 1. Run automated setup
sudo bash scripts/env_setup.sh production

# 2. Configure environment variables
sudo nano .env

# 3. Validate setup
bash scripts/env_validate.sh production

# 4. Start service
sudo systemctl start polymarket-bot
```

### Staging Environment Setup

```bash
# 1. Run automated setup
sudo bash scripts/env_setup.sh staging

# 2. Configure staging environment
sudo nano .env.staging

# 3. Get testnet funds
# Visit: https://faucet.polygon.technology/

# 4. Validate and start
bash scripts/env_validate.sh staging
sudo systemctl start polymarket-bot-staging
```

### Development Environment Setup

```bash
# 1. Run setup
bash scripts/env_setup.sh development

# 2. Configure development settings
nano .env.development

# 3. Activate and validate
source scripts/env_activate.sh development
bash scripts/env_validate.sh development

# 4. Run tests
python -m pytest tests/
```

## Environment Management

### Environment Manager CLI

```bash
# List all environments
python utils/environment_manager.py list

# Create environment
python utils/environment_manager.py create --env production

# Validate environment
python utils/environment_manager.py validate --env production

# Install dependencies
python utils/environment_manager.py install-deps --env production
```

### Multi-Environment Manager

```bash
# Switch environments
python utils/multi_env_manager.py switch --env staging

# Quick switch (no validation)
python utils/multi_env_manager.py quick-switch --env development

# List environments with status
python utils/multi_env_manager.py list

# Validate network compatibility
python utils/multi_env_manager.py validate-network --env production
```

### Environment Activation Scripts

```bash
# Activate production
source scripts/env_activate.sh production

# Activate staging
source scripts/env_activate.sh staging

# Deactivate current environment
source scripts/env_deactivate.sh
```

## Dependency Management

### Dependency Manager CLI

```bash
# Generate requirements files
python utils/dependency_manager.py generate

# Check for vulnerabilities
python utils/dependency_manager.py check-vulns --env production

# Update dependencies (dry run)
python utils/dependency_manager.py update --env production --dry-run

# Install dependencies
python utils/dependency_manager.py install --env production
```

### Requirements Files

Each environment has a specific requirements file:

- `requirements/requirements-production.txt` - Production dependencies
- `requirements/requirements-staging.txt` - Staging + testing tools
- `requirements/requirements-development.txt` - All dependencies + dev tools

### Security Scanning

```bash
# Check for vulnerabilities
python utils/dependency_manager.py check-vulns --env production

# The system uses safety.py for vulnerability scanning
# Results are cached for 24 hours
```

## Environment Validation

### Automated Validation

```bash
# Validate current environment
bash scripts/env_validate.sh

# Validate specific environment
bash scripts/env_validate.sh production
```

### Validation Checks

The validation script checks:

- ✅ Python version compatibility (3.9-3.11)
- ✅ Virtual environment activation
- ✅ Critical dependency availability
- ✅ Environment variable configuration
- ✅ File permissions
- ✅ Project structure integrity
- ✅ Security vulnerability status

### Health Check API

```bash
# Start health check server
python utils/health_check.py serve --port 8000

# Get health status via HTTP
curl http://localhost:8000/health

# Check specific environment
curl http://localhost:8000/health?environment=staging
```

## Health Monitoring

### Health Endpoints

- `GET /health` - Overall health status
- `GET /health/environment` - Environment-specific health
- `GET /health/dependencies` - Dependency status
- `GET /health/reproducibility` - Environment reproducibility check

### Health Status Levels

- 🟢 **healthy** - All systems operational
- 🟡 **degraded** - Minor issues, operational
- 🔴 **unhealthy** - Critical issues, needs attention

### Monitoring Integration

Health checks integrate with:

- Systemd service monitoring
- Log file analysis
- Resource usage monitoring
- Service availability checks

## Environment Repair

### Automatic Repair

```bash
# Diagnose issues
python utils/env_repair.py diagnose --env production

# Automatic repair (medium risk)
python utils/env_repair.py repair --env production --risk medium

# Emergency repair (high risk)
python utils/env_repair.py emergency --env production
```

### Repair Operations

The repair system can fix:

- Corrupted virtual environments
- Missing dependencies
- Configuration issues
- Permission problems
- Service failures

### Backup and Restore

```bash
# Create environment backup
python utils/env_repair.py backup --env production

# Restore from backup
python utils/env_repair.py restore --backup-path /path/to/backup --env production
```

## Multi-Environment Support

### Environment Switching

```bash
# Switch with full validation and backup
python utils/multi_env_manager.py switch --env staging

# Quick switch for development
python utils/multi_env_manager.py quick-switch --env development
```

### Network Configuration

| Environment | Network | Chain ID | Testnet |
|-------------|---------|----------|---------|
| production | Polygon Mainnet | 137 | ❌ |
| staging | Polygon Mumbai | 80001 | ✅ |
| development | Polygon Amoy | 80002 | ✅ |

### Environment Templates

Each environment has a template file:

- `env-production-template.txt` - Mainnet production settings
- `env-staging-template.txt` - Mumbai testnet settings
- `env-development-template.txt` - Amoy testnet development settings

## Troubleshooting

### Common Issues

#### 1. Virtual Environment Issues

**Problem**: `python` command not found in activated environment

**Solution**:
```bash
# Recreate virtual environment
python utils/environment_manager.py create --env production --force

# Reinstall dependencies
python utils/dependency_manager.py install --env production
```

#### 2. Dependency Conflicts

**Problem**: Package installation fails due to conflicts

**Solution**:
```bash
# Check for conflicts
python utils/dependency_manager.py resolve --env production

# Update requirements
python utils/dependency_manager.py update --env production
```

#### 3. Permission Issues

**Problem**: Cannot write to log/data directories

**Solution**:
```bash
# Fix permissions
sudo chown -R polymarket-bot:polymarket-bot logs/ data/

# Set correct permissions
chmod 750 logs/ data/
```

#### 4. Service Won't Start

**Problem**: Systemd service fails to start

**Solution**:
```bash
# Check service status
sudo systemctl status polymarket-bot

# Check logs
sudo journalctl -u polymarket-bot -f

# Validate environment
bash scripts/env_validate.sh production
```

#### 5. Network Connectivity Issues

**Problem**: Cannot connect to Polygon RPC

**Solution**:
```bash
# Test RPC connection
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  $POLYGON_RPC_URL

# Switch RPC endpoint in .env file
# Available endpoints:
# - https://polygon-rpc.com/
# - https://rpc-mainnet.matic.network
# - https://matic-mainnet.chainstacklabs.com
```

### Diagnostic Tools

#### System Diagnostics

```bash
# Run full diagnostic check
bash scripts/diagnostic_check.py

# Check system resources
python -c "import psutil; print(f'CPU: {psutil.cpu_percent()}%, Memory: {psutil.virtual_memory().percent}%')"

# Validate all environments
for env in production staging development; do
  echo "Validating $env..."
  bash scripts/env_validate.sh $env
done
```

#### Log Analysis

```bash
# View recent logs
tail -f logs/environment_manager.log

# Check systemd logs
sudo journalctl -u polymarket-bot -n 100

# Search for errors
grep ERROR logs/*.log
```

### Emergency Procedures

#### Complete Environment Reset

```bash
# Stop all services
sudo systemctl stop polymarket-bot polymarket-bot-staging

# Emergency repair
python utils/env_repair.py emergency --env production

# Reconfigure
cp env-production-template.txt .env
nano .env

# Restart
sudo systemctl start polymarket-bot
```

#### Data Recovery

```bash
# List available backups
ls -la backups/

# Restore from backup
python utils/env_repair.py restore --backup-path backups/env_production_backup_20241225.tar.gz --env production
```

## Best Practices

### Environment Management

1. **Always use staging first**: Test changes in staging before production
2. **Backup before changes**: Create backups before major updates
3. **Validate after changes**: Run validation after any configuration changes
4. **Monitor health**: Regularly check environment health
5. **Keep environments separate**: Never mix testnet and mainnet configurations

### Security Practices

1. **Never commit secrets**: Use environment variables, never commit private keys
2. **Restrict permissions**: Keep environment files readable only by owner
3. **Regular updates**: Keep dependencies updated and scan for vulnerabilities
4. **Network isolation**: Use different wallets for different environments
5. **Access control**: Limit system access to necessary users only

### Development Workflow

1. **Development → Staging → Production**: Always follow this promotion path
2. **Automated testing**: Run tests in all environments before deployment
3. **Version control**: Keep environment configurations in version control (without secrets)
4. **Documentation**: Document any environment-specific changes
5. **Monitoring**: Set up alerts for environment health issues

### Performance Optimization

1. **Resource monitoring**: Monitor CPU, memory, and disk usage
2. **Dependency optimization**: Keep only necessary dependencies installed
3. **Caching**: Use caching for expensive operations
4. **Background processing**: Run intensive tasks in background when possible
5. **Load testing**: Test environment performance under load

### Backup Strategy

1. **Automated backups**: Enable automated backup schedules
2. **Offsite storage**: Store backups in multiple locations
3. **Test restores**: Regularly test backup restoration
4. **Versioned backups**: Keep multiple backup versions
5. **Encrypted backups**: Encrypt sensitive backup data

## API Reference

### Environment Manager

```python
from utils.environment_manager import EnvironmentManager

env_mgr = EnvironmentManager()

# Create environment
env_mgr.create_environment("production")

# Validate environment
health = env_mgr.validate_environment("production")

# Get environment info
info = env_mgr.get_environment_info("production")
```

### Dependency Manager

```python
from utils.dependency_manager import DependencyManager

dep_mgr = DependencyManager()

# Generate requirements
dep_mgr.generate_requirements_files()

# Check vulnerabilities
vulns = dep_mgr.check_vulnerabilities("production")

# Install dependencies
dep_mgr.install_dependencies("production")
```

### Multi-Environment Manager

```python
from utils.multi_env_manager import MultiEnvironmentManager

multi_mgr = MultiEnvironmentManager()

# Switch environments
switch = multi_mgr.switch_environment("staging")

# Get current environment
current = multi_mgr.get_current_environment()

# List environments
envs = multi_mgr.list_available_environments()
```

### Health Check System

```python
from utils.health_check import SystemHealthCheck

health_checker = SystemHealthCheck()

# Check overall health
health = await health_checker.check_overall_health("production")

# Check reproducibility
reproducible = await health_checker.check_environment_reproduction("production")
```

## Support and Maintenance

### Regular Maintenance Tasks

#### Daily
- Check environment health: `python utils/health_check.py check`
- Monitor log files for errors
- Verify service status

#### Weekly
- Update dependencies: `python utils/dependency_manager.py update --dry-run`
- Check for security vulnerabilities
- Validate all environments

#### Monthly
- Full environment validation
- Backup verification
- Performance optimization review

### Getting Help

1. **Check logs**: Review log files in `logs/` directory
2. **Run diagnostics**: Use `bash scripts/diagnostic_check.py`
3. **Validate environment**: Run `bash scripts/env_validate.sh`
4. **Check documentation**: Review this document and inline code documentation
5. **Community support**: Check project issues and discussions

### Contributing

When making changes to the environment management system:

1. Update this documentation
2. Test changes across all environments
3. Add appropriate logging
4. Follow security best practices
5. Validate with automated tests

---

**Version**: 1.0.0
**Last Updated**: December 25, 2025
**Maintainer**: Polymarket Bot Team
