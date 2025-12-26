#!/bin/bash
# Environment Validation Script for Polymarket Copy Bot

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default environment
ENV_NAME="${1:-production}"

echo -e "${BLUE}🔍 Validating Polymarket Copy Bot Environment: ${ENV_NAME}${NC}"
echo "=============================================="

# Check if we're running in the correct environment
if [ "$POLYMARKET_ENV" != "$ENV_NAME" ]; then
    echo -e "${YELLOW}⚠️  Not running in environment '$ENV_NAME'${NC}"
    echo -e "${YELLOW}💡 Activate with: source scripts/env_activate.sh $ENV_NAME${NC}"
fi

# Check Python version
echo -e "${BLUE}🐍 Checking Python version...${NC}"
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 9 ] && [ "$PYTHON_MINOR" -lt 12 ]; then
    echo -e "${GREEN}✅ Python $PYTHON_VERSION is compatible${NC}"
else
    echo -e "${RED}❌ Python $PYTHON_VERSION is not compatible${NC}"
    echo -e "${YELLOW}   Required: Python 3.9 - 3.11${NC}"
    exit 1
fi

# Check virtual environment
echo -e "${BLUE}📦 Checking virtual environment...${NC}"
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}❌ Not running in a virtual environment${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Virtual environment active: $VIRTUAL_ENV${NC}"
fi

# Check critical dependencies
echo -e "${BLUE}📚 Checking critical dependencies...${NC}"
CRITICAL_DEPS=("web3" "pydantic" "tenacity" "cryptography" "requests" "aiohttp")
FAILED_DEPS=()

for dep in "${CRITICAL_DEPS[@]}"; do
    if python -c "import $dep" 2>/dev/null; then
        echo -e "${GREEN}✅ $dep${NC}"
    else
        echo -e "${RED}❌ $dep${NC}"
        FAILED_DEPS+=("$dep")
    fi
done

if [ ${#FAILED_DEPS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Missing critical dependencies: ${FAILED_DEPS[*]}${NC}"
    echo -e "${YELLOW}💡 Install with: python utils/environment_manager.py install-deps --env $ENV_NAME${NC}"
    exit 1
fi

# Check environment variables
echo -e "${BLUE}🔐 Checking environment variables...${NC}"
REQUIRED_VARS=("PRIVATE_KEY" "POLYGON_RPC_URL")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ $var${NC}"
        MISSING_VARS+=("$var")
    else
        echo -e "${GREEN}✅ $var${NC}"
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Missing required environment variables: ${MISSING_VARS[*]}${NC}"
    echo -e "${YELLOW}💡 Configure in your .env file${NC}"
    exit 1
fi

# Check optional environment variables
echo -e "${BLUE}🔧 Checking optional environment variables...${NC}"
OPTIONAL_VARS=("TELEGRAM_BOT_TOKEN" "TELEGRAM_CHAT_ID" "POLYGONSCAN_API_KEY")
for var in "${OPTIONAL_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${YELLOW}⚠️  $var (optional)${NC}"
    else
        echo -e "${GREEN}✅ $var${NC}"
    fi
done

# Check file permissions
echo -e "${BLUE}🔒 Checking file permissions...${NC}"

# Check .env file permissions
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    PERMS=$(stat -c "%a" "$ENV_FILE" 2>/dev/null || stat -f "%A" "$ENV_FILE" 2>/dev/null)
    if [ "$PERMS" = "600" ]; then
        echo -e "${GREEN}✅ .env file permissions${NC}"
    else
        echo -e "${RED}❌ .env file permissions: $PERMS (should be 600)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
fi

# Check log directory permissions
LOG_DIR="$PROJECT_ROOT/logs"
if [ -d "$LOG_DIR" ]; then
    PERMS=$(stat -c "%a" "$LOG_DIR" 2>/dev/null || stat -f "%A" "$LOG_DIR" 2>/dev/null)
    if [ "$PERMS" = "750" ]; then
        echo -e "${GREEN}✅ logs directory permissions${NC}"
    else
        echo -e "${YELLOW}⚠️  logs directory permissions: $PERMS (recommended: 750)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  logs directory not found${NC}"
fi

# Check data directory permissions
DATA_DIR="$PROJECT_ROOT/data"
if [ -d "$DATA_DIR" ]; then
    PERMS=$(stat -c "%a" "$DATA_DIR" 2>/dev/null || stat -f "%A" "$DATA_DIR" 2>/dev/null)
    if [ "$PERMS" = "750" ]; then
        echo -e "${GREEN}✅ data directory permissions${NC}"
    else
        echo -e "${YELLOW}⚠️  data directory permissions: $PERMS (recommended: 750)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  data directory not found${NC}"
fi

# Run Python environment validation
echo -e "${BLUE}🔬 Running Python environment validation...${NC}"
if python -c "
import sys
import os
from pathlib import Path

# Check project structure
project_root = Path('$PROJECT_ROOT')
required_dirs = ['config', 'core', 'utils', 'tests']
for dir_name in required_dirs:
    if not (project_root / dir_name).exists():
        print(f'❌ Missing directory: {dir_name}')
        sys.exit(1)

print('✅ Project structure OK')

# Try importing main modules
try:
    from config.settings import settings
    print('✅ Config module OK')
except ImportError as e:
    print(f'❌ Config import failed: {e}')
    sys.exit(1)

try:
    from core.clob_client import CLOBClient
    print('✅ Core modules OK')
except ImportError as e:
    print(f'❌ Core import failed: {e}')
    sys.exit(1)

print('✅ All Python validations passed')
"; then
    echo -e "${GREEN}✅ Python environment validation passed${NC}"
else
    echo -e "${RED}❌ Python environment validation failed${NC}"
    exit 1
fi

# Check for security issues
echo -e "${BLUE}🛡️  Checking for security issues...${NC}"
if command -v safety >/dev/null 2>&1; then
    echo -e "${BLUE}   Running safety check...${NC}"
    if safety check --bare; then
        echo -e "${GREEN}✅ No known security vulnerabilities${NC}"
    else
        echo -e "${RED}❌ Security vulnerabilities found${NC}"
        echo -e "${YELLOW}💡 Update dependencies or check safety report${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Safety tool not installed (optional)${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Environment validation completed successfully!${NC}"
echo -e "${BLUE}📊 Environment: $ENV_NAME${NC}"
echo -e "${BLUE}🐍 Python: $PYTHON_VERSION${NC}"
echo -e "${BLUE}📦 Virtual env: $VIRTUAL_ENV${NC}"
echo ""
echo -e "${YELLOW}💡 Ready to run the Polymarket Copy Bot!${NC}"
