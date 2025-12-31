# Codebase Search MCP Server

Production-ready codebase search server for Polymarket Copy Bot using Ruff engine.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# List available patterns
python scripts/search_code.py --list-patterns

# Search for money calculation patterns
python scripts/search_code.py --pattern money_calculations

# Search with custom regex
python scripts/search_code.py --custom "circuit_breaker.*is_tripped"
```

## Features

- ✅ Fast Ruff-based pattern matching
- ✅ 1-hour TTL caching
- ✅ Rate limiting (10 requests/minute)
- ✅ Circuit breaker protection
- ✅ Memory-limited cache (10MB)
- ✅ Pre-defined critical patterns
- ✅ Custom regex support
- ✅ JSON/text/compact output

## Files

- `mcp/__init__.py` - Package exports
- `mcp/codebase_search.py` - Main MCP server implementation
- `config/mcp_config.py` - Configuration management
- `scripts/search_code.py` - CLI interface
- `tests/unit/test_codebase_search.py` - Unit tests

## Documentation

See `MCP_CODEBASE_SEARCH_INTEGRATION.md` for full integration guide.

## Tests

```bash
pytest tests/unit/test_codebase_search.py -v
```

## Safety

- READ-ONLY: Does not modify any code
- Preserves all existing risk management
- No changes to money calculations
- Maintains logging and alert systems
- Async/await for non-blocking operations
