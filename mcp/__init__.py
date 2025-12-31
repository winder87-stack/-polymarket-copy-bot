"""MCP Servers Package for Polymarket Copy Trading Bot

This package provides Model Context Protocol (MCP) server implementations that provide
enhanced capabilities for interacting with codebase.

All servers run in isolation with proper resource limits and circuit breakers
to ensure zero performance impact on trading operations.

ACTUAL Package Structure (All files are direct in mcp/):
==========================
mcp/
├── __init__.py (this file - package exports)
├── codebase_search.py (direct file - module: mcp.codebase_search)
│   └── class: CodebaseSearchServer
├── testing_server.py (direct file - module: mcp.testing_server)
│   ├── class: TestingServer
│   ├── class: TestingCircuitBreaker
│   ├── class: TestResult
│   └── class: TestExecutionConfig
├── monitoring_server.py (direct file - module: mcp.monitoring_server)
│   └── class: MonitoringServer
├── monitoring_server_enhanced.py (direct file - module: mcp.monitoring_server)
│   └── class: MonitoringServerEnhanced
└── main_mcp.py (direct file - module: mcp.main_mcp)
    └── class: MCPServerManager

Usage:
    from mcp.codebase_search import CodebaseSearchServer
    from mcp.testing_server import TestingServer, TestingCircuitBreaker
    from mcp.monitoring_server import MonitoringServer
    from mcp.main_mcp import MCPServerManager

Author: Polymarket Bot Team
Date: December 29, 2025
Version: 11.0.0
"""

# Direct imports from actual file structure
# All files are DIRECTLY in mcp/ directory (not in subdirectories)
from .codebase_search import CodebaseSearchServer
from .testing_server import (
    TestingServer,
    TestingCircuitBreaker,
    TestResult,
    TestSuiteResult,
    TestExecutionConfig,
)
from .monitoring_server import MonitoringServer
from .monitoring_server_enhanced import ProductionMonitoringServer
from .main_mcp import MCPServerManager

# Public package exports (for external import as 'from mcp import ...')
__all__ = [
    # Core servers (direct imports from .module_file)
    "CodebaseSearchServer",
    "TestingServer",
    "TestingCircuitBreaker",
    "MonitoringServer",
    "ProductionMonitoringServer",
    # Main manager
    "MCPServerManager",
    # Internal classes (for advanced usage)
    "SearchPattern",
    "SearchResult",
    "SearchCircuitBreaker",
    "RateLimiter",
    "TestResult",
    "TestSuiteResult",
    "TestExecutionConfig",
    "PerformanceSnapshot",
    "SystemHealthCheck",
    "AlertStatus",
]

# Package version
__version__ = "11.0.0"
