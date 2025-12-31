#!/bin/bash
# Poetry Setup Script for Polymarket Copy Trading Bot
# This script installs Poetry and generates poetry.lock

set -e

echo "🔧 Poetry Setup Script for Polymarket Copy Trading Bot"
echo "======================================================"
echo ""

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "📦 Poetry not found. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -

    # Add Poetry to PATH
    export PATH="$HOME/.local/bin:$PATH"

    # Verify installation
    if command -v poetry &> /dev/null; then
        echo "✅ Poetry installed successfully"
        poetry --version
    else
        echo "❌ Poetry installation failed. Please install manually:"
        echo "   curl -sSL https://install.python-poetry.org | python3 -"
        echo "   source $HOME/.local/bin/poetry env use python3"
        exit 1
    fi
else
    echo "✅ Poetry is already installed"
    poetry --version
fi

echo ""
echo "🔒 Generating poetry.lock file..."
echo ""

# Generate lock file without updating dependencies
poetry lock --no-update

if [ -f "poetry.lock" ]; then
    echo "✅ poetry.lock generated successfully"
    echo ""
    echo "📊 Lock file statistics:"
    echo "   Packages locked: $(grep -c "^name = " poetry.lock)"
else
    echo "❌ Failed to generate poetry.lock"
    exit 1
fi

echo ""
echo "🔄 Updating requirements.txt from poetry.lock..."
echo ""

# Export to requirements.txt
poetry export -f requirements.txt --output requirements.txt --without-hashes

if [ -f "requirements.txt" ]; then
    echo "✅ requirements.txt updated from poetry.lock"
else
    echo "❌ Failed to export requirements.txt"
    exit 1
fi

echo ""
echo "✨ Setup complete! Next steps:"
echo "   1. Review pyproject.toml and poetry.lock"
echo "   2. Run 'poetry install' to create virtual environment"
echo "   3. Run 'poetry shell' to activate environment"
echo "   4. Run 'pytest' to verify installation"
echo ""
