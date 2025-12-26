#!/bin/bash
set -e

echo "🏗️ Building API documentation..."

# Install documentation dependencies
pip install -r docs/requirements.txt

# Generate API documentation
sphinx-apidoc -f -o docs/api/ core/ config/ utils/

# Build HTML documentation
cd docs
make clean
make html
cd ..

echo "✅ Documentation built successfully at docs/_build/html/"
echo "🚀 To view: open docs/_build/html/index.html in your browser"

# Auto-deploy to GitHub Pages
if [ "$GITHUB_REF" == "refs/heads/main" ] && [ "$GITHUB_EVENT_NAME" == "push" ]; then
    echo "🚀 Deploying documentation to GitHub Pages..."
    git config user.name "github-actions"
    git config user.email "github-actions@github.com"

    # Create orphan branch for docs
    git checkout --orphan gh-pages
    git reset --hard
    git commit --allow-empty -m "Initial documentation commit"

    # Copy built docs
    mkdir -p docs
    cp -r docs/_build/html/* docs/

    # Add CNAME file for custom domain
    echo "bot.polymarket.example.com" > docs/CNAME

    # Commit and push
    git add docs/
    git commit -m "Update documentation - $(date)"
    git push --force origin gh-pages

    echo "✅ Documentation deployed to GitHub Pages"
fi
