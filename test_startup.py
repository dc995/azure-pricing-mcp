"""Cold-start regression tests for the MCP stdio entry point."""

import json
import queue
import subprocess
import sys
import threading
import asyncio
from pathlib import Path

import pytest


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


def start_server(entrypoint="azure_pricing_mcp.py"):
    process = subprocess.Popen(
        [sys.executable, entrypoint],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    responses = queue.Queue()

    def read_responses():
        for line in process.stdout:
            responses.put(json.loads(line))

    threading.Thread(target=read_responses, daemon=True).start()
    return process, responses


def send(process, request):
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()


def stop_server(process):
    process.terminate()
    process.wait(timeout=5)


@pytest.mark.parametrize("entrypoint", ["azure_pricing_mcp.py", "azure_pricing_server.py"])
def test_initialize_responds_within_two_seconds(entrypoint):
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "startup-test", "version": "1.0"},
        },
    }
    process, responses = start_server(entrypoint)

    try:
        send(process, request)
        response = responses.get(timeout=2.0)
        assert response["id"] == 1
        assert "result" in response
    finally:
        stop_server(process)


def test_tools_are_listed_without_loading_pricing_implementation():
    process, responses = start_server()
    try:
        send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        response = responses.get(timeout=2.0)
        tool_names = {tool["name"] for tool in response["result"]["tools"]}
        assert tool_names == EXPECTED_TOOLS
    finally:
        stop_server(process)


def test_tool_calls_delegate_to_existing_implementation():
    process, responses = start_server()
    try:
        send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_customer_discount", "arguments": {}},
            },
        )
        response = responses.get(timeout=15.0)
        assert response["id"] == 3
        assert "Customer Discount Information" in response["result"]["content"][0]["text"]
    finally:
        stop_server(process)


def test_fast_tool_definitions_match_existing_server():
    from azure_pricing_server import handle_list_tools
    from mcp_tool_definitions import TOOLS

    existing_tools = [
        tool.model_dump(mode="json", by_alias=True, exclude_none=True)
        for tool in asyncio.run(handle_list_tools())
    ]
    assert TOOLS == existing_tools