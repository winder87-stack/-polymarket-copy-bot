#!/bin/bash
# Environment Deactivation Script for Polymarket Copy Bot

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 Deactivating Polymarket Copy Bot Environment${NC}"

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  No virtual environment is currently active${NC}"
else
    echo -e "${BLUE}🐍 Deactivating virtual environment: $VIRTUAL_ENV${NC}"
    deactivate
    echo -e "${GREEN}✅ Virtual environment deactivated${NC}"
fi

# Clear environment variables
unset POLYMARKET_ENV
unset POLYMARKET_PROJECT_ROOT

# Remove project modules from Python path if they were added
if [ -n "$PYTHONPATH" ]; then
    # Remove project root from PYTHONPATH if it exists
    PROJECT_ROOT_TO_REMOVE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    PYTHONPATH=$(echo "$PYTHONPATH" | sed "s|$PROJECT_ROOT_TO_REMOVE:||g" | sed 's|::|:|g' | sed 's|^:||' | sed 's|:$||')
    export PYTHONPATH
fi

echo -e "${GREEN}🎉 Environment deactivated successfully!${NC}"
echo -e "${YELLOW}💡 To reactivate, run: source scripts/env_activate.sh [environment_name]${NC}"
