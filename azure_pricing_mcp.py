#!/usr/bin/env python3
"""Fast-starting MCP stdio entry point for Azure pricing tools."""

import json
import sys

from mcp_tool_definitions import TOOLS


SERVER_INFO = {"name": "azure-pricing", "version": "1.0.0"}


def write_message(message):
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def error_response(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def call_tool(params):
    import asyncio

    from azure_pricing_server import handle_call_tool

    result = asyncio.run(handle_call_tool(params["name"], params.get("arguments", {})))
    return {
        "content": [item.model_dump(mode="json", by_alias=True, exclude_none=True) for item in result]
    }


def handle_request(request):
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        params = request.get("params", {})
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        try:
            result = call_tool(request.get("params", {}))
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as error:
            return error_response(request_id, -32603, str(error))
    if request_id is not None:
        return error_response(request_id, -32601, f"Method not found: {method}")
    return None


def main():
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                write_message(response)
        except Exception as error:
            write_message(error_response(None, -32700, str(error)))


if __name__ == "__main__":
    main()