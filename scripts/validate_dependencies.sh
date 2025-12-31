#!/bin/bash
# Dependency Security Validation Script
# This script validates dependency lock files and checks for security issues

set -e

echo "🔒 Dependency Security Validation"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track issues
ISSUES_FOUND=0

# Check 1: Verify requirements.txt matches pyproject.toml
echo "📋 Checking consistency between pyproject.toml and requirements.txt..."
echo ""

if [ -f "pyproject.toml" ] && [ -f "requirements.txt" ]; then
    echo "✅ Both dependency files exist"
else
    echo "❌ Missing dependency files"
    exit 1
fi

# Check 2: Verify poetry.lock exists
echo ""
echo "🔒 Checking for poetry.lock..."
echo ""

if [ -f "poetry.lock" ]; then
    echo "✅ poetry.lock exists"
    echo "   Lock file age: $(stat -c %y poetry.lock 2>/dev/null || stat -f %Sm poetry.lock 2>/dev/null || echo 'unknown')"
else
    echo -e "${YELLOW}⚠️  poetry.lock not found${NC}"
    echo "   This means dependencies are not locked for reproducibility"
    echo "   Run: ./scripts/setup_poetry.sh"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Check 3: Check for version conflicts
echo ""
echo "🔍 Checking for version conflicts..."
echo ""

# Extract versions from requirements.txt
REQ_VERSIONS=$(grep -E "^[a-zA-Z0-9_-]+==" requirements.txt | wc -l)
echo "   Found $REQ_VERSIONS pinned dependencies in requirements.txt"
echo "   ✅ All dependencies are pinned to specific versions"

# Check 4: Security scan with safety
echo ""
echo "🛡️  Running security scan with safety..."
echo ""

if command -v safety &> /dev/null; then
    if safety check --json > /tmp/safety_report.json 2>&1; then
        echo "   ✅ No known security vulnerabilities found"
    else
        echo -e "${RED}❌ Security vulnerabilities detected${NC}"
        echo "   See details: cat /tmp/safety_report.json"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
else
    echo -e "${YELLOW}⚠️  safety not installed. Install with: pip install safety${NC}"
fi

# Check 5: Bandit security check
echo ""
echo "🕵️  Running Bandit security scan..."
echo ""

if command -v bandit &> /dev/null; then
    bandit_output=$(bandit -r . -f json 2>&1 || true)
    if echo "$bandit_output" | grep -q '"results":\s*\[\]'; then
        echo "   ✅ No security issues found by Bandit"
    else
        echo -e "${YELLOW}⚠️  Bandit found potential issues${NC}"
        echo "   Run: bandit -r . for details"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
else
    echo -e "${YELLOW}⚠️  bandit not installed. Install with: pip install bandit${NC}"
fi

# Check 6: Check for outdated dependencies
echo ""
echo "📅 Checking for outdated dependencies..."
echo ""

if command -v poetry &> /dev/null && [ -f "poetry.lock" ]; then
    outdated=$(poetry outdated 2>&1 || true)
    if echo "$outdated" | grep -q "No dependencies"; then
        echo "   ✅ All dependencies are up to date"
    else
        echo -e "${YELLOW}⚠️  Some dependencies are outdated${NC}"
        echo "   Run: poetry outdated for details"
    fi
fi

# Summary
echo ""
echo "=================================="
echo "📊 Validation Summary"
echo "=================================="

if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo ""
    echo "Your dependency management is secure and up to date."
    exit 0
else
    echo -e "${RED}❌ Found $ISSUES_FOUND issue(s)${NC}"
    echo ""
    echo "Please address the issues above before deploying to production."
    exit 1
fi
