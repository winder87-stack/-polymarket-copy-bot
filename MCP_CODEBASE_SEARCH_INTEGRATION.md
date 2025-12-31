# Codebase Search MCP Server - Integration Guide

## Overview

The `codebase_search` MCP server provides production-ready pattern-based code searching for the Polymarket Copy Bot project. It uses Ruff as the underlying search engine for fast, efficient codebase navigation and analysis.

### Key Features

- **Fast Search**: Uses Ruff for blazing-fast pattern matching
- **Caching**: 1-hour TTL cache to avoid repeated scans
- **Rate Limiting**: 10 searches/minute to prevent system overload
- **Circuit Breaker**: Automatic protection during high system load
- **Memory Management**: Bounded cache with 10MB limit
- **Pre-defined Patterns**: Critical patterns for money calculations, risk controls, variable conflicts, and API endpoints

## Installation & Setup

### 1. Dependencies

The MCP server requires Ruff for code searching. Install with:

```bash
pip install ruff
```

Ruff is already included in `requirements.txt`, so ensure you run:

```bash
pip install -r requirements.txt
```

### 2. Configuration

Configuration is managed via `config/mcp_config.py`. The server uses these environment variables:

| Environment Variable | Default | Description |
|-------------------|----------|-------------|
| `CODEBASE_SEARCH_ENABLED` | `true` | Enable/disable the MCP server |
| `CODEBASE_SEARCH_CACHE_ENABLED` | `true` | Enable result caching |

Add to your `.env` file:

```bash
CODEBASE_SEARCH_ENABLED=true
CODEBASE_SEARCH_CACHE_ENABLED=true
```

## Pre-defined Search Patterns

The server includes these pre-configured patterns:

### 1. Money Calculations (`money_calculations`)
- **Pattern**: `(account_balance|risk_percent|position_size)\s*[\*\+\/-]`
- **Purpose**: Identify money/price calculations
- **Severity**: Warning
- **Category**: Financial

### 2. Risk Controls (`risk_controls`)
- **Pattern**: `circuit_breaker|is_tripped|max_position_size|max_daily_loss`
- **Purpose**: Find risk management and circuit breaker logic
- **Severity**: Error
- **Category**: Risk

### 3. Variable Conflicts (`variable_conflicts`)
- **Pattern**: `for\s+time\s+in|import\s+time`
- **Purpose**: Detect potential variable naming conflicts (e.g., using `time` as loop variable)
- **Severity**: Warning
- **Category**: Code Quality

### 4. API Endpoints (`api_endpoints`)
- **Pattern**: `polymarket\.com/api|quicknode\.pro`
- **Purpose**: Locate API endpoint URLs and RPC endpoints
- **Severity**: Info
- **Category**: Network

## Usage

### CLI Usage

The CLI script provides an easy interface for codebase searching:

```bash
# List all available patterns
python scripts/search_code.py --list-patterns

# Search for a predefined pattern
python scripts/search_code.py --pattern money_calculations

# Search in specific directories
python scripts/search_code.py --pattern risk_controls --directory core/ utils/

# Include test files in search
python scripts/search_code.py --pattern api_endpoints --include-tests

# Use custom regex pattern
python scripts/search_code.py --custom "def.*trade.*\("

# Limit results
python scripts/search_code.py --pattern money_calculations --max-results 20

# Disable cache for this search
python scripts/search_code.py --pattern risk_controls --no-cache

# Output in JSON format
python scripts/search_code.py --pattern money_calculations --output json

# Get server statistics
python scripts/search_code.py --stats

# Clear search cache
python scripts/search_code.py --clear-cache
```

### Programmatic Usage

#### Basic Usage

```python
import asyncio
from mcp.codebase_search import CodebaseSearchServer

async def search_example():
    server = CodebaseSearchServer()

    # Search for money calculation patterns
    results = await server.search_pattern("money_calculations")

    for result in results:
        print(f"Found in {result.file_path}:{result.line_number}")
        print(f"  {result.line_content}")

    await server.shutdown()

asyncio.run(search_example())
```

#### Custom Patterns

```python
async def custom_search_example():
    server = CodebaseSearchServer()

    # Search for custom regex pattern
    results = await server.search_custom_pattern(
        regex_pattern=r"circuit_breaker\.is_tripped\(\)",
        target_directories=["core/", "trading/"],
    )

    for result in results:
        print(f"Match: {result.matched_text}")

    await server.shutdown()

asyncio.run(custom_search_example())
```

#### Using Singleton

```python
from mcp.codebase_search import get_search_server

async def singleton_example():
    server = get_search_server()

    # Server is shared across the application
    results = await server.search_pattern("risk_controls")

    # Get statistics
    stats = server.get_stats()
    print(f"Cache hit ratio: {stats['cache_hit_ratio']:.1%}")

    await server.shutdown()

asyncio.run(singleton_example())
```

### Integration with `main.py`

To integrate the MCP server into the main application:

#### Step 1: Import in `main.py`

```python
from mcp.codebase_search import get_search_server
```

#### Step 2: Initialize in `PolymarketCopyBot.__init__()`

```python
class PolymarketCopyBot:
    def __init__(self) -> None:
        # ... existing initialization ...

        # Initialize codebase search server
        self.codebase_search_server = get_search_server()
```

#### Step 3: Add cleanup in `shutdown()` method

```python
async def shutdown(self):
    # ... existing shutdown code ...

    # Shutdown codebase search server
    if self.codebase_search_server:
        await self.codebase_search_server.shutdown()
        logger.info("✅ Codebase search server stopped")
```

#### Step 4: Add to health check (optional)

```python
async def health_check(self) -> bool:
    # ... existing health checks ...

    # Check codebase search server health
    if self.codebase_search_server:
        try:
            stats = self.codebase_search_server.get_stats()
            if stats["circuit_breaker_state"] == "open":
                logger.warning("⚠️ Codebase search circuit breaker is open")
                return False
        except Exception as e:
            logger.error(f"Codebase search health check failed: {e}")
            return False

    return True
```

## API Endpoint Integration

If your application uses FastAPI, you can add a search endpoint:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class SearchRequest(BaseModel):
    pattern_name: str
    target_directories: Optional[List[str]] = None
    include_tests: bool = False
    max_results: Optional[int] = None

@app.post("/api/search")
async def search_codebase(request: SearchRequest):
    """
    Search codebase for a pattern.

    Returns JSON results with search matches and context.
    """
    try:
        server = get_search_server()
        results = await server.search_pattern(
            pattern_name=request.pattern_name,
            target_directories=request.target_directories,
            include_tests=request.include_tests,
            max_results=request.max_results,
        )

        return {
            "success": True,
            "pattern": request.pattern_name,
            "count": len(results),
            "results": [result.to_dict() for result in results],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

@app.get("/api/search/patterns")
async def list_patterns():
    """List all available search patterns."""
    server = get_search_server()
    return server.list_patterns()

@app.get("/api/search/stats")
async def get_search_stats():
    """Get search server statistics."""
    server = get_search_server()
    return server.get_stats()
```

## Custom Patterns

You can add custom patterns to the configuration:

```python
from config.mcp_config import get_codebase_search_config

# Get configuration
config = get_codebase_search_config()

# Add custom pattern
config.add_custom_pattern(
    name="high_risk_functions",
    pattern=r"(execute_trade|place_order|approve)\s*\(",
    description="High-risk trading functions",
    category="risk",
    severity="error",
)

# Now you can search for it
results = await server.search_pattern("high_risk_functions")
```

## Troubleshooting

### Circuit Breaker Active

If you see "Circuit breaker is active" errors:

1. Wait 60 seconds for automatic recovery
2. Check system load with: `python scripts/search_code.py --stats`
3. Review circuit breaker failures in logs
4. Reduce search frequency

### Rate Limit Exceeded

If you see rate limit errors:

1. Wait: `python scripts/search_code.py --stats` shows wait time
2. Cache results to avoid repeated searches
3. Increase rate limit in configuration if needed

### No Results Found

If searches return no results:

1. Check that pattern name is correct: `python scripts/search_code.py --list-patterns`
2. Include test files if needed: `--include-tests`
3. Search in specific directories: `--directory core/`
4. Use custom regex for more flexibility: `--custom "your_pattern"`

### Ruff Not Found

If Ruff is not installed:

```bash
pip install ruff
```

Or install from `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Testing

### Run Unit Tests

```bash
pytest tests/unit/test_codebase_search.py -v
```

### Test CLI

```bash
# Test basic search
python scripts/search_code.py --pattern money_calculations

# Test list patterns
python scripts/search_code.py --list-patterns

# Test stats
python scripts/search_code.py --stats
```

### Integration Test

```bash
python -m mcp.codebase_search
```

## Performance

### Cache Performance

The server uses a bounded cache with:
- **Max size**: 100 entries
- **TTL**: 3600 seconds (1 hour)
- **Memory limit**: 10 MB

Check cache performance:

```bash
python scripts/search_code.py --stats
```

### Rate Limiting

- **Default limit**: 10 searches/minute
- **Wait time**: Up to 60 seconds when limit exceeded
- **Sliding window**: Tracks last 60 seconds of requests

### Circuit Breaker

- **Failure threshold**: 5 consecutive failures
- **Recovery timeout**: 60 seconds
- **States**: closed → open → half-open → closed

## Production Safety Features

### 1. Circuit Breaker Protection

Prevents search operations during high system load. Automatically opens after 5 consecutive failures.

### 2. Rate Limiting

Prevents system overload by limiting search frequency to 10 requests/minute.

### 3. Memory Limits

Bounded cache ensures memory usage stays under 10 MB, with automatic eviction of old entries.

### 4. Timeout Protection

Each search operation times out after 30 seconds to prevent hanging.

### 5. Permission Checks

Only allows searching in configured project directories (prevents accessing system files).

### 6. Thread Safety

All operations use async/await patterns with proper locking for shared state.

## Monitoring

### Log Messages

The server logs these events:

```
INFO CodebaseSearchServer initialized
INFO Cache hit for pattern: money_calculations
WARNING Circuit breaker is tripped, rejecting search request
WARNING Rate limit exceeded: 15/10 requests in last minute
ERROR Search failed for pattern money_calculations: <error details>
```

### Statistics

Monitor server health:

```bash
python scripts/search_code.py --stats
```

Output includes:
- Total searches performed
- Cache hit/miss ratio
- Circuit breaker state
- Rate limiter request count
- Memory usage estimates

## Critical Constraints

### DO NOT Modify These Items

- **Risk Management Logic**: The MCP server is READ-ONLY. It does not modify any code.
- **Money Calculation Patterns**: Pre-defined patterns are critical for financial safety.
- **API Endpoint Configurations**: MCP server only searches, does not change RPC URLs.
- **Logging Formats**: Preserves all existing logging structures.
- **Alert Systems**: Does not interfere with Telegram alerts or error reporting.

### PRESERVED Safety Features

- ✅ All existing risk management logic
- ✅ Circuit breaker protection in trading
- ✅ Position sizing calculations using Decimal
- ✅ Transaction validation
- ✅ Memory management with BoundedCache
- ✅ Async/await patterns for non-blocking operations

## Quick Reference

### Common Commands

```bash
# List patterns
python scripts/search_code.py --list-patterns

# Search money calculations
python scripts/search_code.py --pattern money_calculations

# Search risk controls
python scripts/search_code.py --pattern risk_controls

# Search variable conflicts
python scripts/search_code.py --pattern variable_conflicts

# Search API endpoints
python scripts/search_code.py --pattern api_endpoints

# Custom search
python scripts/search_code.py --custom "import.*time"

# Include tests
python scripts/search_code.py --pattern money_calculations --include-tests

# Get stats
python scripts/search_code.py --stats
```

### Environment Variables

```bash
# Enable/disable MCP server
export CODEBASE_SEARCH_ENABLED=true

# Enable/disable caching
export CODEBASE_SEARCH_CACHE_ENABLED=true
```

## Support

For issues or questions:

1. Check logs in `logs/` directory
2. Run health check: `python scripts/search_code.py --stats`
3. Review circuit breaker state
4. Check rate limiter status
5. Verify Ruff installation: `ruff --version`

## License

MIT License - See project root for details.
