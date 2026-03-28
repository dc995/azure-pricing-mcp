# Quick Start Guide

## Prerequisites

- Python 3.8+
- An MCP-compatible client (GitHub Copilot CLI, Claude Desktop, VS Code/Cursor, etc.)

## Setup (3 steps)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Bootstrap the Service Catalog

```bash
python sync_catalog.py
```

This creates `azure_services.db` from `service_catalog.json`. Run this once, and again whenever you update the catalog.

### 3. Configure Your MCP Client

Add the server to your client's MCP configuration:

**GitHub Copilot CLI** — add to `mcp.json`:
```json
{
  "servers": {
    "azure-pricing": {
      "type": "stdio",
      "command": "python",
      "args": ["azure_pricing_server.py"],
      "cwd": "C:\\path\\to\\azure-pricing-mcp"
    }
  }
}
```

**Claude Desktop** — add to `claude_desktop_config.json`:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "azure-pricing": {
      "command": "python",
      "args": ["-m", "azure_pricing_server"],
      "cwd": "/path/to/azure-pricing-mcp"
    }
  }
}
```

**VS Code / Cursor** — add to `settings.json`:
```json
{
  "mcp": {
    "servers": {
      "azure-pricing": {
        "command": "python",
        "args": ["-m", "azure_pricing_server"],
        "cwd": "/path/to/azure-pricing-mcp"
      }
    }
  }
}
```

Restart your client after adding the configuration.

## Verify It Works

Ask your AI assistant any of these:

- *"What Azure services are available for AI?"*
- *"Show me SQL Managed Instance SKUs in East US 2"*
- *"Estimate costs for a D4s_v3 VM running 8 hours a day"*
- *"Compare Azure Kubernetes Service pricing across eastus and westeurope"*
- *"What's the monthly cost of a Fabric F64 capacity?"*

## Running Tests

```bash
python -m pytest test_catalog_sync.py -v
```

## Updating the Service Catalog

To discover new Azure services or check coverage:

```bash
python sync_catalog.py --from-api --report
```

To add a service, edit `service_catalog.json` and re-run `python sync_catalog.py`. See [ADDING_SERVICES.md](ADDING_SERVICES.md) for the full workflow.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No module named 'mcp'" | Run `pip install -r requirements.txt` |
| "Service catalog DB not found" | Run `python sync_catalog.py` |
| Server not responding in client | Check path in MCP config, restart client |
| No results for a service | Check spelling — service names are case-sensitive. Use `azure_sku_discovery` for fuzzy matching. |

## Next Steps

- [ADDING_SERVICES.md](ADDING_SERVICES.md) — How to add new services
- [CAPABILITIES.md](CAPABILITIES.md) — Full tool reference
- [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) — Detailed query examples
- [COVERAGE_GAP_LOG.md](COVERAGE_GAP_LOG.md) — Known limitations