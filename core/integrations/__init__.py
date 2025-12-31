"""Core integrations package.

This package provides integration between MCP servers and the core trading system:
- codebase_search: Auto-detect risk parameter usage patterns
- testing: Verify test coverage thresholds
- monitoring: Real-time risk parameter monitoring

All integrations maintain zero performance impact on trading operations.
"""

from .mcp_risk_integration import (
    MCPRiskIntegrator,
    get_mcp_risk_integrator,
)

__all__ = [
    "MCPRiskIntegrator",
    "get_mcp_risk_integrator",
]

__version__ = "1.0.0"
