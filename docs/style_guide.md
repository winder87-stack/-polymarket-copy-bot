# Python Style Guide

This document defines the coding standards and style guidelines for the Polymarket Copy Trading Bot project.

## Overview

This project follows PEP 8 with some modifications for consistency and readability. All code must pass automated linting and formatting checks before being merged.

## Code Formatting

### Tools

- **autopep8**: Automatic PEP 8 code formatting (aggressive mode)
- **black**: Code formatter (configured in `pyproject.toml`)
- **isort**: Import sorting (configured to work with black)
- **mypy**: Static type checking

### Line Length

- **Maximum**: 100 characters
- **Rationale**: Balances readability with modern wide screens

### Indentation

- **Spaces**: 4 spaces per indentation level
- **No tabs**: Tabs are not allowed
- **Continuation**: Align continuation lines with opening delimiter or use hanging indent

```python
# Good
def function_name(
    param1: str,
    param2: int,
    param3: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Function docstring."""
    pass

# Also acceptable
result = some_function(
    arg1, arg2, arg3,
    arg4, arg5
)
```

## Type Hints

### Requirements

- **All functions** must have type hints for parameters and return types
- **All class methods** must have type hints
- **Use `Optional[T]`** for nullable values
- **Use `Union[T1, T2]`** for multiple types (prefer `|` in Python 3.10+)
- **Avoid `Any`** when possible - use specific types

### Examples

```python
from typing import Dict, List, Optional, Any

# Good - complete type hints
def calculate_position_size(
    original_amount: float,
    account_balance: float,
    max_position_size: float,
    risk_percentage: float = 0.01,
) -> float:
    """Calculate position size based on risk management rules."""
    pass

# Good - Optional type
def get_account_balance(account_id: str) -> Optional[Decimal]:
    """Get account balance or None if not found."""
    pass

# Good - Dict type hints
def process_trade_data(
    trade: Dict[str, Any],
    market_data: Dict[str, float],
) -> Dict[str, Any]:
    """Process trade data with market information."""
    pass

# Avoid - missing type hints
def bad_function(param1, param2):
    """Missing type hints."""
    pass
```

## Constants

### Naming

- **UPPER_SNAKE_CASE**: All constants must be in uppercase with underscores
- **Module-level**: Define constants at module level
- **Group related constants**: Use classes or dictionaries for related constants

### Magic Numbers

- **Never use magic numbers**: Replace with named constants
- **Document purpose**: Add comments explaining why constants have specific values

### Examples

```python
# Good - named constants
DEFAULT_RISK_PERCENTAGE = 0.01  # 1% risk per trade
MAX_POSITION_SIZE_USD = 50.0
MIN_TRADE_AMOUNT_USD = 1.0
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 3600  # 1 hour
CONSECUTIVE_LOSS_THRESHOLD = 5
FAILURE_RATE_THRESHOLD = 0.5  # 50%

# Bad - magic numbers
def calculate_risk(amount: float) -> float:
    return amount * 0.01  # What is 0.01?

# Good - using constants
def calculate_risk(amount: float) -> float:
    return amount * DEFAULT_RISK_PERCENTAGE
```

## Docstrings

### Style

- **Google Style**: All docstrings must follow Google style guide
- **Required for**: All modules, classes, and functions
- **Language**: English

### Format

```python
def function_name(param1: str, param2: int) -> Dict[str, Any]:
    """Brief one-line description.

    Longer description if needed. Can span multiple lines and explain
    the function's purpose, behavior, and any important details.

    Args:
        param1: Description of param1. Include units, constraints, etc.
        param2: Description of param2. Explain valid ranges.

    Returns:
        Description of return value. Include structure if returning dict/list.

    Raises:
        ValueError: When param1 is invalid.
        APIError: When external API call fails.

    Examples:
        >>> result = function_name("test", 42)
        >>> print(result["key"])
        'value'

    Note:
        Any additional notes about usage, performance, or edge cases.
    """
    pass
```

### Class Docstrings

```python
class ClassName:
    """Brief class description.

    Longer description explaining the class's purpose, main responsibilities,
    and key design decisions.

    Attributes:
        attribute1: Description of attribute1.
        attribute2: Description of attribute2.

    Example:
        >>> instance = ClassName(param1, param2)
        >>> instance.method()
        result
    """

    def __init__(self, param1: str, param2: int) -> None:
        """Initialize class instance.

        Args:
            param1: Description of param1.
            param2: Description of param2.
        """
        self.attribute1 = param1
        self.attribute2 = param2
```

## Import Organization

### Order

1. Standard library imports
2. Third-party imports
3. Local application imports

### Formatting

- **One import per line** (except for `from` imports)
- **Group imports** with blank lines between groups
- **Sort imports** alphabetically within groups
- **Use `isort`** for automatic sorting

```python
# Standard library
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Third-party
import aiohttp
from pydantic import BaseModel, Field

# Local
from config.settings import settings
from core.exceptions import APIError
from utils.helpers import normalize_address
```

## Naming Conventions

### Variables and Functions

- **snake_case**: All lowercase with underscores
- **Descriptive**: Names should clearly indicate purpose
- **Avoid abbreviations**: Use full words unless abbreviation is standard

```python
# Good
account_balance_usdc = 1000.0
max_position_size = 50.0
calculate_position_size()

# Bad
bal = 1000.0
mps = 50.0
calc_pos()
```

### Classes

- **PascalCase**: First letter of each word capitalized
- **Descriptive**: Class names should be nouns

```python
# Good
class TradeExecutor:
    pass

class AccountManager:
    pass

# Bad
class executor:
    pass

class account_mgr:
    pass
```

### Constants

- **UPPER_SNAKE_CASE**: All uppercase with underscores

```python
# Good
MAX_POSITION_SIZE = 50.0
DEFAULT_RISK_PERCENTAGE = 0.01

# Bad
maxPositionSize = 50.0
defaultRiskPercentage = 0.01
```

### Private Methods/Attributes

- **Leading underscore**: Use `_` prefix for private/internal methods and attributes
- **Double underscore**: Avoid `__` prefix (name mangling) unless necessary

```python
class MyClass:
    def __init__(self) -> None:
        self.public_attr = "public"
        self._private_attr = "private"
        self.__mangled_attr = "mangled"  # Avoid unless necessary

    def public_method(self) -> None:
        """Public method."""
        pass

    def _private_method(self) -> None:
        """Private method - internal use only."""
        pass
```

## Error Handling

### Exception Types

- **Use specific exceptions**: Don't catch generic `Exception` unless necessary
- **Custom exceptions**: Use project-specific exceptions from `core/exceptions.py`
- **Document exceptions**: Include `Raises` section in docstrings

```python
# Good
try:
    result = await api_call()
except aiohttp.ClientError as e:
    logger.error(f"Network error: {e}")
    raise APIError(f"API call failed: {e}") from e
except ValidationError as e:
    logger.warning(f"Invalid data: {e}")
    return None

# Bad
try:
    result = await api_call()
except Exception as e:
    logger.error(f"Error: {e}")
```

## Code Quality

### Complexity

- **Cyclomatic complexity**: Keep functions simple (target < 10)
- **Function length**: Prefer shorter functions (< 50 lines)
- **Class size**: Keep classes focused (single responsibility)

### Comments

- **Explain why, not what**: Comments should explain reasoning, not restate code
- **Update with code**: Keep comments synchronized with code changes
- **Remove dead code**: Delete commented-out code

```python
# Good - explains why
# Use Decimal for financial calculations to avoid floating-point errors
amount = Decimal(str(value))

# Bad - restates what code does
# Convert value to Decimal
amount = Decimal(str(value))
```

### Testing

- **Test coverage**: Maintain 90%+ coverage
- **Test naming**: `test_<functionality>_<scenario>`
- **Test organization**: Group related tests in classes

## Pre-commit Hooks

### Setup

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

### Hooks Configured

- **autopep8**: Format code to PEP 8
- **isort**: Sort imports
- **black**: Format code (if enabled)
- **mypy**: Type checking
- **flake8**: Linting (if enabled)

## CI/CD Integration

### Checks

- **PEP 8 compliance**: All code must pass PEP 8 checks
- **Type checking**: All code must pass mypy checks
- **Test coverage**: Must maintain 90%+ coverage
- **Linting**: All code must pass linting checks

### Failure Behavior

- **Block PRs**: PRs with style violations are blocked
- **Auto-fix**: Some violations can be auto-fixed
- **Manual review**: Complex violations require manual review

## Backward Compatibility

### Configuration Files

- **No breaking changes**: Style improvements must not break existing configs
- **Deprecation warnings**: Use warnings for deprecated features
- **Version compatibility**: Maintain compatibility with existing config schemas

## Examples

### Complete Example

```python
"""Module for calculating position sizes with risk management.

This module provides functions for calculating optimal position sizes
based on account balance, risk tolerance, and market conditions.
"""

import logging
from decimal import Decimal
from typing import Optional

# Constants
DEFAULT_RISK_PERCENTAGE = 0.01  # 1% risk per trade
MIN_POSITION_SIZE_USD = 1.0  # Minimum $1 position
MAX_POSITION_SIZE_USD = 50.0  # Maximum $50 position

logger = logging.getLogger(__name__)


def calculate_position_size(
    original_amount: float,
    account_balance: float,
    max_position_size: float = MAX_POSITION_SIZE_USD,
    risk_percentage: float = DEFAULT_RISK_PERCENTAGE,
) -> float:
    """Calculate position size based on risk management rules.

    Calculates the optimal position size using a risk-based approach
    that limits exposure to a percentage of account balance while
    respecting maximum position size constraints.

    Args:
        original_amount: Original trade amount in USD.
        account_balance: Current account balance in USD.
        max_position_size: Maximum allowed position size in USD.
            Defaults to MAX_POSITION_SIZE_USD.
        risk_percentage: Risk percentage per trade (0.01 = 1%).
            Defaults to DEFAULT_RISK_PERCENTAGE.

    Returns:
        Calculated position size in USD. Will be at least
        MIN_POSITION_SIZE_USD and at most max_position_size.

    Raises:
        ValueError: If account_balance is negative or zero.

    Example:
        >>> size = calculate_position_size(100.0, 1000.0)
        >>> assert MIN_POSITION_SIZE_USD <= size <= MAX_POSITION_SIZE_USD
    """
    if account_balance <= 0:
        raise ValueError("Account balance must be positive")

    # Calculate risk-based size (percentage of account)
    risk_based_size = account_balance * risk_percentage

    # Calculate proportional size (10% of original trade)
    proportional_size = original_amount * 0.1

    # Take minimum of both approaches, capped by max position size
    position_size = min(risk_based_size, proportional_size, max_position_size)

    # Ensure minimum trade amount
    position_size = max(position_size, MIN_POSITION_SIZE_USD)

    logger.debug(
        f"Position size calculated: ${position_size:.2f} "
        f"(risk-based: ${risk_based_size:.2f}, "
        f"proportional: ${proportional_size:.2f})"
    )

    return position_size
```

## Tools and Commands

### Format Code

```bash
# Run autopep8 aggressively
autopep8 --in-place --aggressive --aggressive --recursive .

# Run black
black .

# Sort imports
isort .
```

### Check Code

```bash
# Type checking
mypy .

# Linting
flake8 .

# Check PEP 8
pycodestyle .
```

### Pre-commit

```bash
# Run all hooks
pre-commit run --all-files

# Run specific hook
pre-commit run autopep8 --all-files
```

## References

- [PEP 8](https://pep8.org/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Type Hints (PEP 484)](https://www.python.org/dev/peps/pep-0484/)
- [Docstring Conventions (PEP 257)](https://www.python.org/dev/peps/pep-0257/)
