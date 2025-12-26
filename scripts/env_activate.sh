#!/bin/bash
# Environment Activation Script for Polymarket Copy Bot
# Usage: source scripts/env_activate.sh [environment_name]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default environment
ENV_NAME="${1:-production}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 Activating Polymarket Copy Bot Environment: ${ENV_NAME}${NC}"

# Validate environment
case "$ENV_NAME" in
    production|staging|development)
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: ${ENV_NAME}${NC}"
        echo -e "${YELLOW}Valid environments: production, staging, development${NC}"
        return 1 2>/dev/null || exit 1
        ;;
esac

# Set environment-specific paths
if [ "$ENV_NAME" = "production" ]; then
    VENV_PATH="$PROJECT_ROOT/venv"
    ENV_FILE="$PROJECT_ROOT/.env"
elif [ "$ENV_NAME" = "staging" ]; then
    VENV_PATH="$PROJECT_ROOT/environments/staging/venv"
    ENV_FILE="$PROJECT_ROOT/.env.staging"
else # development
    VENV_PATH="$PROJECT_ROOT/environments/development/venv"
    ENV_FILE="$PROJECT_ROOT/.env.development"
fi

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ Virtual environment not found: $VENV_PATH${NC}"
    echo -e "${YELLOW}💡 Run: python utils/environment_manager.py create --env $ENV_NAME${NC}"
    return 1 2>/dev/null || exit 1
fi

# Check if activation script exists
ACTIVATE_SCRIPT="$VENV_PATH/bin/activate"
if [ ! -f "$ACTIVATE_SCRIPT" ]; then
    echo -e "${RED}❌ Activation script not found: $ACTIVATE_SCRIPT${NC}"
    return 1 2>/dev/null || exit 1
fi

# Activate virtual environment
echo -e "${BLUE}🐍 Activating virtual environment...${NC}"
source "$ACTIVATE_SCRIPT"

# Set environment variables
if [ -f "$ENV_FILE" ]; then
    echo -e "${BLUE}🔐 Loading environment variables from $ENV_FILE${NC}"
    set -a
    source "$ENV_FILE"
    set +a
else
    echo -e "${YELLOW}⚠️  Environment file not found: $ENV_FILE${NC}"
    echo -e "${YELLOW}💡 Create it from the template: cp env-${ENV_NAME}-template.txt $ENV_FILE${NC}"
fi

# Set additional environment variables
export POLYMARKET_ENV="$ENV_NAME"
export POLYMARKET_PROJECT_ROOT="$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Change to project root
cd "$PROJECT_ROOT"

# Validate environment
echo -e "${BLUE}🔍 Validating environment...${NC}"
if python -c "import sys; print(f'Python: {sys.version}')"; then
    echo -e "${GREEN}✅ Python environment activated${NC}"
else
    echo -e "${RED}❌ Python environment validation failed${NC}"
    return 1 2>/dev/null || exit 1
fi

# Show environment info
echo -e "${GREEN}🎉 Environment '$ENV_NAME' activated successfully!${NC}"
echo -e "${BLUE}📍 Project root: $PROJECT_ROOT${NC}"
echo -e "${BLUE}🐍 Python: $(python --version)${NC}"
echo -e "${BLUE}📦 Virtual env: $VENV_PATH${NC}"

# Show available commands
echo -e "${YELLOW}💡 Available commands:${NC}"
echo -e "   python main.py                 # Run main bot"
echo -e "   python -m pytest tests/        # Run tests"
echo -e "   python utils/environment_manager.py validate --env $ENV_NAME  # Validate environment"
echo -e "   deactivate                     # Deactivate environment"
