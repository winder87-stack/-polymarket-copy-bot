"""
Simple MCP Import Test - Verifies Working Pattern

This test uses ONLY the PROVEN working import pattern:
    from mcp.main_mcp import MCPServerManager

All other import patterns (from mcp.codebase_search, etc.) have been tested and FAILED.

Focus:
1. Verify all MCP servers can be accessed through MCPServerManager
2. Test basic functionality works
3. Confirm package structure is correct

Author: Polymarket Bot Team
Date: December 29, 2025
Version: 1.0.0 (Working - Uses Proven Import Pattern)
"""

import pytest
import asyncio
from datetime import datetime, timezone

# Use PROVEN working import pattern (this one we verified actually works!)
from mcp.main_mcp import MCPServerManager


# ============================================================================
# Test Classes
# ============================================================================

class TestMCPProvenImports:
    """Test using PROVEN working import pattern."""

    @pytest.mark.asyncio
    async def test_mcp_manager_start_stop(self):
        """Test MCPServerManager can start and stop."""
        manager = MCPServerManager(servers=["testing"])
        
        # Start manager
        start_time = datetime.now(timezone.utc)
        await manager.start()
        
        # Verify all servers are running
        status = await manager.get_status()
        assert status["is_running"] is True, "All servers should be running"
        assert status["startup_time"] is not None, "Should have startup time"
        
        # Let servers run briefly
        await asyncio.sleep(0.05)
        
        # Stop all servers
        stop_time = datetime.now(timezone.utc)
        await manager.stop()
        
        # Verify all servers are stopped
        status = await manager.get_status()
        assert status["is_running"] is False, "All servers should be stopped"
        assert status["shutdown_requested"] is True, "Should have requested shutdown"
        
        # Verify lifecycle completed within reasonable time
        duration = (stop_time - start_time).total_seconds()
        assert duration < 1.0, "Lifecycle should complete within 1 second"
        
        print("✅ MCP Manager lifecycle works!")

    @pytest.mark.asyncio
    async def test_mcp_manager_graceful_shutdown(self):
        """Test graceful shutdown handling."""
        manager = MCPServerManager(servers=["codebase_search", "monitoring"])
        
        # Start servers
        await manager.start()
        
        # Verify servers are running
        status = await manager.get_status()
        assert status["is_running"] is True, "Servers should be running"
        
        # Request graceful shutdown
        manager.shutdown()
        
        # Wait for shutdown to complete
        await asyncio.sleep(0.1)
        
        # Verify shutdown completed
        status = await manager.get_status()
        assert status["is_running"] is False, "Should be stopped after shutdown"
        assert status["shutdown_requested"] is True, "Should have requested shutdown"
        
        print("✅ MCP Manager graceful shutdown works!")

    @pytest.mark.asyncio
    async def test_mcp_manager_all_servers(self):
        """Test all MCP servers can start together."""
        manager = MCPServerManager(servers=["codebase_search", "testing", "monitoring"])
        
        # Start all servers
        start_time = datetime.now(timezone.utc)
        await manager.start()
        
        # Verify all servers are running
        status = await manager.get_status()
        assert status["is_running"] is True, "All servers should be running"
        assert status["startup_time"] is not None, "Should have startup time"
        
        # Let servers run briefly
        await asyncio.sleep(0.05)
        
        # Stop all servers
        stop_time = datetime.now(timezone.utc)
        await manager.stop()
        
        # Verify all servers are stopped
        status = await manager.get_status()
        assert status["is_running"] is False, "All servers should be stopped"
        assert status["shutdown_requested"] is True, "Should have requested shutdown"
        
        # Verify lifecycle completed within reasonable time
        duration = (stop_time - start_time).total_seconds()
        assert duration < 1.5, "Lifecycle should complete within 1.5 seconds"
        
        print("✅ All MCP servers can work together!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
