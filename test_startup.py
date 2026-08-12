"""MCP SDK v2 lifecycle and backward-compatibility tests."""

import asyncio
import sys
import time
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError
from mcp.types.version import LATEST_HANDSHAKE_VERSION, LATEST_MODERN_VERSION

import azure_pricing_server


ROOT = Path(__file__).resolve().parent
EXPECTED_TOOLS = {
    "azure_cost_estimate",
    "azure_discover_skus",
    "azure_price_compare",
    "azure_price_search",
    "azure_service_discovery",
    "azure_sku_discovery",
    "get_customer_discount",
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_protocol"),
    [("auto", LATEST_MODERN_VERSION), ("legacy", LATEST_HANDSHAKE_VERSION)],
)
async def test_server_supports_modern_and_legacy_clients(mode, expected_protocol):
    async with Client(azure_pricing_server.server, mode=mode) as client:
        tools = await client.list_tools()
        result = await client.call_tool("get_customer_discount", {})

        assert client.protocol_version == expected_protocol
        assert client.server_info.version == "2.0.2"
        assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS
        assert not result.is_error
        assert "Customer Discount Information" in result.content[0].text


@pytest.mark.asyncio
async def test_legacy_ping_is_not_blocked_by_tool_call(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()
    original_handler = azure_pricing_server.handle_call_tool

    async def delayed_tool(name, arguments):
        started.set()
        await release.wait()
        return await original_handler(name, arguments)

    monkeypatch.setattr(azure_pricing_server, "handle_call_tool", delayed_tool)

    async with Client(azure_pricing_server.server, mode="legacy") as client:
        tool_call = asyncio.create_task(client.call_tool("get_customer_discount", {}))
        await asyncio.wait_for(started.wait(), timeout=1)
        await asyncio.wait_for(client.send_ping(), timeout=1)
        release.set()
        result = await tool_call

    assert not result.is_error


@pytest.mark.asyncio
async def test_tool_cancellation_reaches_the_handler(monkeypatch):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def cancellable_tool(name, arguments):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(azure_pricing_server, "handle_call_tool", cancellable_tool)

    async with Client(azure_pricing_server.server, mode="legacy") as client:
        tool_call = asyncio.create_task(client.call_tool("get_customer_discount", {}))
        await asyncio.wait_for(started.wait(), timeout=1)
        tool_call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tool_call
        await asyncio.wait_for(cancelled.wait(), timeout=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("entrypoint", ["azure_pricing_mcp.py", "azure_pricing_server.py"])
async def test_stdio_entrypoints_support_legacy_clients(entrypoint):
    target = StdioServerParameters(
        command=sys.executable,
        args=[entrypoint],
        cwd=ROOT,
    )

    async with asyncio.timeout(10):
        async with Client(stdio_client(target), mode="legacy") as client:
            tools = await client.list_tools()

            assert client.protocol_version == LATEST_HANDSHAKE_VERSION
            assert client.server_info.version == "2.0.2"
            assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_modern_stdio_connection_completes_within_five_seconds():
    target = StdioServerParameters(
        command=sys.executable,
        args=["azure_pricing_mcp.py"],
        cwd=ROOT,
    )
    started = time.perf_counter()

    async with asyncio.timeout(5):
        async with Client(stdio_client(target), mode="auto") as client:
            elapsed = time.perf_counter() - started

            assert client.protocol_version == LATEST_MODERN_VERSION
            assert elapsed < 5


@pytest.mark.asyncio
async def test_unknown_tool_raises_an_mcp_error():
    async with Client(azure_pricing_server.server) as client:
        with pytest.raises(MCPError, match="Internal server error"):
            await client.call_tool("not-a-tool", {})
