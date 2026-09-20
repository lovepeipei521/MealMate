# app/agent/tools/mcp/__init__.py
"""
MCP (Model Context Protocol) module for CookHero.

Provides StreamableHTTP client and setup helpers for MCP server integration.
"""

from app.agent.tools.mcp.client import MCPClient

__all__ = [
    "MCPClient",
]
