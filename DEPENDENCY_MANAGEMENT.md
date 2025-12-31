# Dependency Management Guide

## Overview

This project uses **Poetry** as the primary dependency management tool for enhanced security, reproducibility, and maintainability. The `pyproject.toml` file is the **single source of truth** for all dependencies.

## File Structure

```
polymarket-copy-bot/
├── pyproject.toml          # Source of truth for dependencies (version 1.0.1)
├── poetry.lock             # Locked dependency versions (auto-generated)
├── requirements.txt        # Exported from poetry.lock (auto-generated)
├── requirements.txt.backup # Backup of old requirements (for reference)
└── scripts/
    ├── setup_poetry.sh          # Poetry installation and lock file generation
    └── validate_dependencies.sh # Security validation script
```

## Dependency Sources

### Production Dependencies (pyproject.toml)

All production dependencies are pinned to specific versions in `pyproject.toml`:

```toml
[tool.poetry.dependencies]
python = "^3.9"
py-clob-client = "0.34.1"
web3 = "6.17.0"
eth-account = "0.10.0"
python-dotenv = "1.0.0"
requests = "2.31.0"
aiohttp = "3.9.3"
websockets = "12.0"
pandas = "2.1.4"
matplotlib = "3.8.2"
apscheduler = "3.10.4"
python-telegram-bot = "20.7"
cryptography = "41.0.7"
loguru = "0.7.2"
python-json-logger = "2.0.7"
tenacity = "8.2.3"
psutil = "5.9.8"
prometheus-client = "0.19.0"
uvloop = "0.19.0"
aiofiles = "23.2.1"
aiosignal = "1.3.1"
frozenlist = "1.4.0"
multidict = "6.0.4"
yarl = "1.9.2"
attrs = "23.1.0"
typing_extensions = "4.8.0"
certifi = "2023.7.22"
charset-normalizer = "3.2.0"
idna = "3.4"
pydantic = "2.6.0"
```

### Development Dependencies

```toml
[tool.poetry.group.dev.dependencies]
pytest = "7.4.3"
pytest-asyncio = "0.21.1"
pytest-cov = "4.1.0"
ruff = "0.6.0"
mypy = "1.7.1"
```

### Security Dependencies

```toml
[tool.poetry.group.security.dependencies]
bandit = "1.7.5"
safety = "2.3.5"
```

## Setup Instructions

### Initial Setup

1. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   export PATH="$HOME/.local/bin:$PATH"
   ```

2. **Run the setup script**:
   ```bash
   ./scripts/setup_poetry.sh
   ```

   This script will:
   - Install Poetry if not present
   - Generate `poetry.lock` from `pyproject.toml`
   - Export `requirements.txt` from `poetry.lock`

3. **Create virtual environment**:
   ```bash
   poetry install
   ```

4. **Activate the virtual environment**:
   ```bash
   poetry shell
   ```

### Alternative Installation (without Poetry)

If you prefer to use pip directly:

```bash
pip install -r requirements.txt
```

**Note:** This method is not recommended for production as it bypasses the lock file and may lead to dependency conflicts.

## Dependency Management Workflow

### Adding a New Dependency

**Using Poetry (Recommended):**

```bash
# Add a production dependency
poetry add package-name==1.0.0

# Add a development dependency
poetry add --group dev package-name==1.0.0

# Add a security dependency
poetry add --group security package-name==1.0.0
```

**Manual (Not Recommended):**

1. Add the package to `pyproject.toml` in the appropriate section
2. Run: `poetry lock --no-update`
3. Run: `poetry export -f requirements.txt --output requirements.txt --without-hashes`

### Updating Dependencies

```bash
# Update all dependencies (use with caution)
poetry update

# Update specific package
poetry update package-name

# Check for outdated dependencies
poetry outdated
```

**Warning:** Always test thoroughly after updating dependencies. Never update dependencies during market hours (08:00-16:00 UTC).

### Removing Dependencies

```bash
poetry remove package-name
```

## Security Validation

### Run Security Checks

```bash
# Validate dependency security
./scripts/validate_dependencies.sh
```

This script will:
1. Check consistency between `pyproject.toml` and `requirements.txt`
2. Verify `poetry.lock` exists
3. Run `safety` to check for known vulnerabilities
4. Run `bandit` for security code issues
5. Check for outdated dependencies

### Manual Security Checks

```bash
# Check for known vulnerabilities
safety check

# Run bandit security scan
bandit -r .

# Check for outdated packages
poetry outdated
```

## Version Conflicts

All version conflicts have been resolved as of December 28, 2025:

| Package | Old Version (requirements.txt) | Old Version (pyproject.toml) | Resolved Version |
|---------|-------------------------------|------------------------------|------------------|
| py-clob-client | 0.34.1 | 0.16.0 | **0.34.1** |
| web3 | 6.17.0 | 6.15.1 | **6.17.0** |
| python-telegram-bot | 20.6 | 20.7 | **20.7** |
| aiohttp | 3.9.3 | 3.9.1 | **3.9.3** |

**Note:** We chose the newer, more stable versions from `requirements.txt` while maintaining consistency in `pyproject.toml`.

## Best Practices

### 1. Always Use Poetry for Production

```bash
# ✅ Good - Use Poetry
poetry install
poetry run python main.py

# ❌ Bad - Use pip directly
pip install -r requirements.txt
python main.py
```

### 2. Keep poetry.lock in Git

The `poetry.lock` file MUST be committed to version control:

```bash
git add pyproject.toml poetry.lock
git commit -m "Update dependencies"
```

### 3. Pin All Versions

All dependencies must be pinned to specific versions:

```toml
# ✅ Good - Pinned version
py-clob-client = "0.34.1"

# ❌ Bad - Unpinned version
py-clob-client = "^0.34.1"
```

### 4. Update During Low Risk Periods

Never update dependencies during trading hours (08:00-16:00 UTC). Update during:

- Maintenance windows (weekends, holidays)
- Before major releases
- After thorough testing in staging

### 5. Test After Updates

Always run the full test suite after updating dependencies:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=.

# Run type checking
mypy core/ utils/ --ignore-missing-imports

# Run linting
ruff check . --fix
ruff format .
```

## Troubleshooting

### Poetry Not Found

```bash
# Check if poetry is in PATH
which poetry

# If not found, add to PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Lock File Out of Sync

```bash
# Regenerate lock file
poetry lock --no-update

# If that fails, clear cache and regenerate
poetry cache clear pypi --all
poetry lock --no-update
```

### Dependency Conflicts

```bash
# Check conflict details
poetry show --tree

# Resolve by updating conflicting package
poetry update conflicting-package
```

### Installation Fails

```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Reinstall
poetry install --force-reinstall
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Dependency Check

on: [push, pull_request]

jobs:
  validate-dependencies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
          echo "$HOME/.local/bin" >> $GITHUB_PATH
      - name: Validate dependencies
        run: ./scripts/validate_dependencies.sh
      - name: Install dependencies
        run: poetry install
      - name: Run tests
        run: poetry run pytest tests/ -v
```

## Audit Trail

| Date | Action | Version |
|------|--------|---------|
| 2025-12-28 | Initial dependency management setup | 1.0.1 |
| 2025-12-28 | Resolved version conflicts between requirements.txt and pyproject.toml | 1.0.1 |
| 2025-12-28 | Added poetry.lock generation script | 1.0.1 |
| 2025-12-28 | Added dependency security validation script | 1.0.1 |

## References

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Safety Documentation](https://pyup.io/safety/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [PEP 508 - Dependency Specification](https://www.python.org/dev/peps/pep-0508/)

## Support

For questions about dependency management:

1. Check this documentation
2. Run `./scripts/validate_dependencies.sh`
3. Review error logs in `logs/`
4. Contact the development team

---

**Last Updated:** December 28, 2025
**Maintained By:** Polymarket Bot Team
