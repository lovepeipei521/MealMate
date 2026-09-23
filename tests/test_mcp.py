"""Unit tests for the MCP client and setup integration."""

from __future__ import annotations

import pytest

from app.agent.registry import AgentHub
from app.agent.tools.mcp import setup as mcp_setup
from app.agent.tools.mcp.client import MCPClient
from app.agent.tools.providers.mcp import MCPToolProvider
from app.agent.types import ToolResult


@pytest.fixture(autouse=True)
def reset_agent_hub():
    """Keep MCP tests independent from global AgentHub state."""
    AgentHub.clear_all()
    yield
    AgentHub.clear_all()


@pytest.mark.asyncio
async def test_mcp_client(monkeypatch):
    """Verify the MCP client protocol methods without external network calls."""
    client = MCPClient("https://mcp.example/mcp")
    requests: list[tuple[str, dict | None]] = []

    async def fake_send_request(method, params=None):
        requests.append((method, params))

        if method == "initialize":
            return {"protocolVersion": "2024-11-05"}

        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "maps_weather",
                        "description": "Query weather",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                        },
                    }
                ]
            }

        if method == "tools/call":
            return {"content": [{"type": "text", "text": "苏州天气晴，26℃"}]}

        raise AssertionError(f"Unexpected MCP method: {method}")

    monkeypatch.setattr(client, "_send_request", fake_send_request)

    initialize_result = await client.initialize()
    tools = await client.list_tools()
    tool_result = await client.call_tool("maps_weather", {"city": "苏州"})

    assert initialize_result["protocolVersion"] == "2024-11-05"
    assert tools[0]["name"] == "maps_weather"
    assert tool_result == ToolResult(success=True, data="苏州天气晴，26℃")
    assert [request[0] for request in requests] == [
        "initialize",
        "tools/list",
        "tools/call",
    ]
    assert requests[-1][1] == {
        "name": "maps_weather",
        "arguments": {"city": "苏州"},
    }


@pytest.mark.asyncio
async def test_mcp_registry(monkeypatch):
    """Verify the public MCP setup entry registers Amap for the MCP provider."""
    from app.config import settings

    provider = MCPToolProvider()
    AgentHub.register_provider(provider)

    monkeypatch.setattr(settings.mcp.amap, "enabled", True)
    monkeypatch.setattr(settings.mcp, "amap_api_key", "test-amap-key")

    loaded_servers: list[str] = []

    async def fake_load_server_tools(self, name):
        loaded_servers.append(name)
        return []

    async def skip_custom_servers():
        return None

    monkeypatch.setattr(MCPToolProvider, "load_server_tools", fake_load_server_tools)
    monkeypatch.setattr(
        mcp_setup,
        "_register_custom_mcp_servers",
        skip_custom_servers,
    )

    await mcp_setup.register_mcp_servers()

    assert provider.list_servers() == ["amap"]
    assert provider._servers["amap"] == (
        "https://mcp.amap.com/mcp?key=test-amap-key"
    )
    assert loaded_servers == ["amap"]


@pytest.mark.asyncio
async def test_mcp_registry_skips_without_api_key(monkeypatch):
    """A missing Amap key should skip registration instead of failing startup."""
    from app.config import settings

    provider = MCPToolProvider()
    AgentHub.register_provider(provider)

    monkeypatch.setattr(settings.mcp.amap, "enabled", True)
    monkeypatch.setattr(settings.mcp, "amap_api_key", None)

    async def fail_if_called(self, name):
        raise AssertionError("MCP tools must not load without an Amap API key")

    async def skip_custom_servers():
        return None

    monkeypatch.setattr(MCPToolProvider, "load_server_tools", fail_if_called)
    monkeypatch.setattr(
        mcp_setup,
        "_register_custom_mcp_servers",
        skip_custom_servers,
    )

    await mcp_setup.register_mcp_servers()

    assert provider.list_servers() == []


@pytest.mark.asyncio
async def test_tool_execution(monkeypatch):
    """Verify an MCPTool delegates execution through MCPClient."""
    from app.agent.tools.base import MCPTool

    captured: dict[str, object] = {}

    async def fake_call_tool(self, name, arguments):
        captured["endpoint"] = self.endpoint
        captured["name"] = name
        captured["arguments"] = arguments
        return ToolResult(success=True, data={"city": "苏州", "weather": "晴"})

    monkeypatch.setattr(MCPClient, "call_tool", fake_call_tool)

    tool = MCPTool(
        name="mcp_amap_maps_weather",
        description="Query weather",
        mcp_endpoint="https://mcp.amap.com/mcp?key=test-amap-key",
        mcp_tool_name="maps_weather",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
    )

    result = await tool.execute(city="苏州")

    assert result.success is True
    assert result.data == {"city": "苏州", "weather": "晴"}
    assert captured == {
        "endpoint": "https://mcp.amap.com/mcp?key=test-amap-key",
        "name": "maps_weather",
        "arguments": {"city": "苏州"},
    }
