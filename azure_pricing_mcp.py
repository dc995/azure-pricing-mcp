#!/usr/bin/env python3
"""MCP SDK v2 stdio entry point for Azure pricing tools."""

import asyncio

from azure_pricing_server import main


if __name__ == "__main__":
    asyncio.run(main())