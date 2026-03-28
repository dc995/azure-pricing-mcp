# Contributing to Azure Pricing MCP Server

Thanks for your interest in contributing! This project is a data-driven MCP server
for Azure pricing, and most contributions involve expanding the service catalog
rather than writing Python code.

## Getting Started

1. Fork the repository
2. Clone your fork
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Sync the catalog to SQLite:
   ```bash
   python sync_catalog.py
   ```
5. Run the test suite:
   ```bash
   pytest
   ```

## Development Workflow

Never create PRs from your fork's `main` branch. Always create a dedicated branch:

```bash
# Good — dedicated branch per PR
git checkout -b catalog/add-media-services origin/main
git checkout -b fix/sku-validation-edge-case origin/main

# Bad — PR from main accumulates unrelated commits
git checkout main  # Don't PR from here
```

Branch naming conventions:

- `catalog/*` — Service alias additions or changes to `service_catalog.json`
- `fix/*` — Bug fixes
- `feat/*` — New MCP tools or server features
- `sync/*` — Changes to `sync_catalog.py` or catalog pipeline
- `test/*` — Test coverage improvements
- `docs/*` — Documentation only

## Design Philosophy: Data Over Code

`service_catalog.json` is the single source of truth for all Azure service aliases,
categories, and deprecation metadata. The server loads this data into SQLite at
sync time and reads from SQLite at runtime.

**The core rule:** Adding an Azure service should never require a Python code change.
If you find yourself editing `azure_pricing_server.py` to add a service, something
is wrong.

Code changes are reserved for:

- New MCP tools or tool parameters
- Server behavior (retry logic, response formatting, error handling)
- Sync pipeline improvements (`sync_catalog.py`)
- Test infrastructure

## Adding Azure Services

This is the most common contribution. The short version:

1. Find the exact `serviceName` from the Azure Retail Prices API (case-sensitive)
2. Add alias entries to `service_catalog.json`
3. Run `python sync_catalog.py`
4. Run `pytest` to verify

For the full workflow with examples, API queries, and deprecated service handling,
see [ADDING_SERVICES.md](ADDING_SERVICES.md).

To discover services missing from the catalog:

```bash
python sync_catalog.py --from-api --report
```

Check [COVERAGE_GAP_LOG.md](COVERAGE_GAP_LOG.md) for known gaps and priorities.

## Code Style

- Python 3.10+
- Standard library conventions; no formatter is enforced yet
- Keep `azure_pricing_server.py` as the single server module
- Aliases in `service_catalog.json` must be **lowercase** — the server lowercases
  all user input before matching
- `serviceName` values must match the Azure Retail Prices API **exactly**
  (case-sensitive)

## Testing

Run the full suite (86+ tests including 40 parametrized alias lookups):

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

**What to test for each change type:**

| Change | What to verify |
|--------|---------------|
| New aliases in `service_catalog.json` | `pytest` passes; alias resolves in parametrized lookup tests |
| Server behavior changes | Add/update tests in `test_catalog_sync.py` |
| Sync pipeline changes | Run `python sync_catalog.py --dry-run` then `pytest` |
| Coverage gaps | Run `python sync_catalog.py --from-api --report` |

## Commit Messages

- Use present tense: "Add feature" not "Added feature"
- Keep the first line under 72 characters
- Use a tag prefix to indicate the change area:

```
catalog: Add Azure Managed Grafana aliases
server: Fix SKU validation for consumption-only services
sync: Add --prune-orphans flag to sync_catalog.py
test: Add parametrized tests for IoT service aliases
docs: Update COVERAGE_GAP_LOG with Analytics gaps
```

## What to Contribute

Good first contributions:

- New service aliases from `COVERAGE_GAP_LOG.md` gaps
- Documentation fixes or clarifications
- Test coverage for untested alias lookups
- Deprecated service entries for retired Azure services

For larger changes — new MCP tools, server refactors, sync pipeline redesign —
please open an issue first to discuss the approach.

## Questions?

Open an issue. We're happy to help.
