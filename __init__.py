"""Azure Pricing MCP Server

A Model Context Protocol server for querying Azure retail pricing information.
"""

try:
    from .azure_pricing_server import main
except ImportError:
    # Direct execution or pytest — skip relative import
    pass

__version__ = "1.0.0"
__all__ = ["main"]