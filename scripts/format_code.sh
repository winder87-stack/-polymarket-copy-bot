#!/bin/bash
# Format all Python code using autopep8 with aggressive settings

set -e

echo "🔧 Formatting Python code with autopep8..."

# Find all Python files excluding venv, __pycache__, etc.
find . -type f -name "*.py" \
  -not -path "./venv/*" \
  -not -path "./.venv/*" \
  -not -path "./__pycache__/*" \
  -not -path "./build/*" \
  -not -path "./dist/*" \
  -not -path "./.git/*" \
  -not -path "./htmlcov/*" \
  -not -path "./.mypy_cache/*" \
  -print0 | while IFS= read -r -d '' file; do
    echo "Formatting: $file"
    autopep8 --in-place --aggressive --aggressive --max-line-length=100 \
      --ignore=E501,W503 "$file"
done

echo "✅ Code formatting complete!"

# Also run isort for import sorting
echo "📦 Sorting imports with isort..."
isort . --profile=black --line-length=100 --skip=venv,.venv,build,dist

echo "✅ Import sorting complete!"
