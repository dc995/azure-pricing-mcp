# Azure Pricing MCP Server — Capabilities Reference

> **Version**: 1.0.0
> A comprehensive guide to every capability provided by the Azure Pricing MCP Server.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [MCP Tools Reference](#mcp-tools-reference)
   - [azure_price_search](#1-azure_price_search)
   - [azure_price_compare](#2-azure_price_compare)
   - [azure_cost_estimate](#3-azure_cost_estimate)
   - [azure_discover_skus](#4-azure_discover_skus)
   - [azure_sku_discovery](#5-azure_sku_discovery)
   - [get_customer_discount](#6-get_customer_discount)
4. [Core Capabilities](#core-capabilities)
   - [Real-Time Pricing Retrieval](#real-time-pricing-retrieval)
   - [Cost Estimation & Projection](#cost-estimation--projection)
   - [Multi-Region Price Comparison](#multi-region-price-comparison)
   - [SKU Discovery & Fuzzy Matching](#sku-discovery--fuzzy-matching)
   - [Savings Plan & Reserved Instance Analysis](#savings-plan--reserved-instance-analysis)
   - [Customer Discount Application](#customer-discount-application)
   - [Multi-Currency Support](#multi-currency-support)
5. [Workflow Capabilities](#workflow-capabilities)
   - [Generate an Estimate for the Azure Pricing Calculator (APC) Portal](#generate-an-estimate-for-the-azure-pricing-calculator-apc-portal)
   - [Import a Set of Services (Bulk Pricing)](#import-a-set-of-services-bulk-pricing)
   - [Architecture Cost Modelling](#architecture-cost-modelling)
   - [Budget Forecasting](#budget-forecasting)
   - [Cost Optimization Analysis](#cost-optimization-analysis)
6. [API Integration Details](#api-integration-details)
7. [Filtering & Query Language](#filtering--query-language)
8. [Error Handling & Resilience](#error-handling--resilience)
9. [Supported Azure Services (Aliases)](#supported-azure-services-aliases)
10. [Configuration & Deployment](#configuration--deployment)
11. [Limitations & Known Constraints](#limitations--known-constraints)

---

## Overview

The Azure Pricing MCP Server is a **Model Context Protocol (MCP)** server that gives AI assistants (Claude, GitHub Copilot, etc.) the ability to query, compare, and estimate Azure cloud costs in real time. It acts as a bridge between natural-language conversations and the official [Azure Retail Prices REST API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices).

### What You Can Do

| Capability | Description |
|---|---|
| **Look up any Azure price** | Query retail prices for any Azure service, SKU, region, and currency |
| **Compare across regions** | Side-by-side price comparison for the same service in multiple Azure regions |
| **Estimate monthly/yearly costs** | Project costs based on custom usage patterns (e.g. 8 hrs/day, 5 days/week) |
| **Discover available SKUs** | List every SKU available for a service, with pricing and region availability |
| **Fuzzy service search** | Use everyday terms ("vm", "web app", "k8s") and get the correct Azure service |
| **Analyse savings plans** | Automatically surface 1-year and 3-year savings plan pricing alongside on-demand |
| **Apply customer discounts** | Layer enterprise/negotiated discount percentages on top of retail prices |
| **Multi-currency output** | Return pricing in USD, EUR, GBP, JPY, AUD, or any supported currency |
| **Generate APC-ready estimates** | Produce structured cost breakdowns that map to the Azure Pricing Calculator |
| **Bulk-price a service list** | Import a list of services/SKUs and get pricing for the entire set in one pass |

---

## Architecture

```
┌──────────────────────┐       stdio / MCP        ┌──────────────────────────┐
│  AI Assistant         │ ◄──────────────────────► │  Azure Pricing MCP       │
│  (Claude, Copilot)    │     Tool calls & results │  Server (Python)         │
└──────────────────────┘                           └────────────┬─────────────┘
                                                                │ HTTPS
                                                                ▼
                                                   ┌──────────────────────────┐
                                                   │  Azure Retail Prices API │
                                                   │  prices.azure.com        │
                                                   │  (public, no auth)       │
                                                   └──────────────────────────┘
```

- **Transport**: stdio (standard MCP transport)
- **Runtime**: Python 3.8+ with asyncio
- **HTTP Client**: aiohttp (async, non-blocking)
- **Schema Validation**: Pydantic v2

---

## MCP Tools Reference

### 1. `azure_price_search`

**Purpose**: Search Azure retail prices with flexible filtering, SKU validation, and optional discount.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `service_name` | string | No | — | Azure service name (e.g. `"Virtual Machines"`, `"Storage"`) |
| `service_family` | string | No | — | Service family (e.g. `"Compute"`, `"Databases"`) |
| `region` | string | No | — | Azure region (e.g. `"eastus"`, `"westeurope"`) |
| `sku_name` | string | No | — | SKU name, partial match supported (e.g. `"D2s v3"`) |
| `price_type` | string | No | — | `"Consumption"`, `"Reservation"`, or `"DevTestConsumption"` |
| `currency_code` | string | No | `"USD"` | ISO 4217 currency code |
| `limit` | integer | No | `50` | Maximum number of results (up to 1000) |
| `discount_percentage` | number | No | — | Percentage discount to apply (e.g. `10` for 10%) |
| `validate_sku` | boolean | No | `true` | When true, suggests alternatives if SKU is not found |

**Example prompt**: *"What's the price of a Standard_D2s_v3 VM in East US?"*

**Key behaviours**:
- When `validate_sku` is enabled and no results are found, the server searches for similar SKUs and returns suggestions.
- When too many results match a SKU (>10), a clarification message is returned with the top 5 matches.
- Customer discount (default 10%) is automatically applied unless overridden.
- Savings plan pricing is included when available from the API.

---

### 2. `azure_price_compare`

**Purpose**: Compare prices for the same service across multiple regions or across different SKUs within a region.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `service_name` | string | **Yes** | — | Azure service name to compare |
| `sku_name` | string | No | — | Specific SKU to compare |
| `regions` | array[string] | No | — | List of regions to compare; if omitted, compares SKUs |
| `currency_code` | string | No | `"USD"` | ISO 4217 currency code |
| `discount_percentage` | number | No | — | Percentage discount to apply |

**Example prompt**: *"Compare D4s_v3 VM pricing across eastus, westeurope, and southeastasia."*

**Key behaviours**:
- **Region mode** (when `regions` is provided): Queries each region separately and returns a sorted comparison table.
- **SKU mode** (when `regions` is omitted): Returns all unique SKUs for the service, grouped and sorted by price.
- Results are always sorted cheapest-first.

---

### 3. `azure_cost_estimate`

**Purpose**: Estimate monthly, daily, and yearly costs based on custom usage patterns. This is the primary tool for **generating estimates that can be reflected in the Azure Pricing Calculator (APC) portal**.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `service_name` | string | **Yes** | — | Azure service name |
| `sku_name` | string | **Yes** | — | SKU name |
| `region` | string | **Yes** | — | Azure region |
| `hours_per_month` | number | No | `730` | Expected usage hours/month (730 = full month, 24×30.4) |
| `currency_code` | string | No | `"USD"` | ISO 4217 currency code |
| `discount_percentage` | number | No | — | Percentage discount to apply |

**Output includes**:
- **On-demand pricing**: hourly, daily, monthly, and yearly costs
- **Savings plan analysis**: for each available term (1-year, 3-year), shows the rate, projected cost, percentage saved, and annual dollar savings
- **Discount breakdown**: when a discount is applied, both original and discounted prices are shown at every level
- **Usage assumptions**: echo of the input hours for auditability

**Example prompt**: *"Estimate costs for running a Standard_D4s_v3 VM 12 hours a day in West Europe, with a 15% enterprise discount."*

---

### 4. `azure_discover_skus`

**Purpose**: List all available SKUs for a specific Azure service, with optional region and price-type filters.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `service_name` | string | **Yes** | — | Exact Azure service name |
| `region` | string | No | — | Filter to a specific region |
| `price_type` | string | No | `"Consumption"` | Price type filter |
| `limit` | integer | No | `100` | Maximum number of SKUs to return |

**Output includes**:
- Deduplicated list of SKUs sorted alphabetically
- For each SKU: name, ARM SKU name, product name, sample price, unit of measure, meter name
- List of regions where the SKU is available

---

### 5. `azure_sku_discovery`

**Purpose**: **Intelligent SKU discovery** with fuzzy service-name matching. This is the user-friendly entry point — use everyday terms and the server maps them to exact Azure service names.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `service_hint` | string | **Yes** | — | Natural-language service description (e.g. `"web app"`, `"k8s"`, `"serverless"`) |
| `region` | string | No | — | Optional region filter |
| `currency_code` | string | No | `"USD"` | ISO 4217 currency code |
| `limit` | integer | No | `30` | Maximum number of results |

**Key behaviours**:
- First attempts an exact Azure API match.
- Falls back to a built-in alias dictionary (30+ mappings) for common terms.
- If still no match, performs a broad search and substring-matches against all service and product names.
- Returns results grouped by product with minimum prices and region counts.
- When no match is found, returns up to 5 suggested services with sample SKUs.

---

### 6. `get_customer_discount`

**Purpose**: Retrieve the current customer discount configuration.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `customer_id` | string | No | `"default"` | Customer identifier |

**Current behaviour**: Returns a default 10% standard discount for all customers. Designed to be extended with a customer database or external discount API.

**Output includes**: `customer_id`, `discount_percentage`, `discount_type`, `description`, `valid_until`, `applicable_services`.

---

## Core Capabilities

### Real-Time Pricing Retrieval

- Queries the live **Azure Retail Prices API** (`https://prices.azure.com/api/retail/prices`).
- API version: `2023-01-01-preview` (includes savings plan data).
- No authentication required — the API is public.
- Returns current retail prices including meter-level detail.

### Cost Estimation & Projection

The `azure_cost_estimate` tool converts hourly rates into actionable cost projections:

| Time Period | Calculation |
|---|---|
| Hourly | Direct from API |
| Daily | `hourly_rate × 24` |
| Monthly | `hourly_rate × hours_per_month` |
| Yearly | `monthly_cost × 12` |

Customise `hours_per_month` for real-world usage patterns:
- **Full month (24/7)**: `730` hours (default)
- **Business hours (8h × 22 weekdays)**: `176` hours
- **Dev/test (8h × 5 days × 4 weeks)**: `160` hours
- **Specific schedule**: any custom value

### Multi-Region Price Comparison

Query the same service across multiple Azure regions in a single call. The server:
1. Issues parallel queries per region.
2. Normalises results into a unified comparison table.
3. Sorts by price (cheapest first).
4. Highlights price differentials between regions.

### SKU Discovery & Fuzzy Matching

Two-tier discovery system:

1. **Exact discovery** (`azure_discover_skus`): When you know the exact Azure service name.
2. **Fuzzy discovery** (`azure_sku_discovery`): When you use common terms, abbreviations, or colloquial names.

Built-in alias mappings include:

| User Input | Maps To |
|---|---|
| `vm`, `virtual machine`, `compute` | Virtual Machines |
| `app service`, `web app`, `websites` | Azure App Service |
| `sql`, `database`, `sql server` | Azure SQL Database |
| `kubernetes`, `aks`, `k8s` | Azure Kubernetes Service |
| `functions`, `serverless` | Azure Functions |
| `cosmos`, `cosmosdb`, `document db` | Azure Cosmos DB |
| `redis`, `cache` | Azure Cache for Redis |
| `openai` | Azure OpenAI |
| `storage`, `blob`, `disk` | Storage |
| `load balancer`, `lb` | Load Balancer |
| `app gateway` | Application Gateway |
| `ai`, `cognitive`, `cognitive services` | Azure AI services |
| `networking`, `vnet` | Virtual Network |

### Savings Plan & Reserved Instance Analysis

When the API returns savings plan data for a SKU, the server automatically:
- Lists each available term (typically 1-year and 3-year).
- Calculates the hourly, monthly, and yearly cost under the savings plan.
- Computes the percentage savings vs. on-demand pricing.
- Calculates the absolute annual dollar savings.

This enables direct comparison between on-demand, 1-year, and 3-year commitment options.

### Customer Discount Application

- A configurable discount percentage is applied on top of retail prices.
- When active, both the **original** and **discounted** prices are shown.
- Discounts propagate through all pricing tiers including savings plans.
- The response includes a total savings summary.

### Multi-Currency Support

Pass any supported ISO 4217 currency code to get pricing in that currency:

`USD`, `EUR`, `GBP`, `JPY`, `AUD`, `CAD`, `CHF`, `CNY`, `DKK`, `INR`, `KRW`, `NOK`, `NZD`, `SEK`, `TWD`, `BRL`, and more.

The currency is passed directly to the Azure API, which handles conversion.

---

## Workflow Capabilities

These capabilities describe end-to-end workflows enabled by combining the MCP tools.

### Generate an Estimate for the Azure Pricing Calculator (APC) Portal

The server can produce structured cost breakdowns that mirror what you would manually configure in the [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/).

**Workflow**:
1. Use `azure_sku_discovery` to find the correct service and SKU names for each component in your architecture.
2. Use `azure_cost_estimate` for each service/SKU/region combination with your expected usage hours.
3. The output includes:
   - Per-service hourly, daily, monthly, and yearly costs
   - Savings plan pricing with annual savings calculations
   - Customer discount breakdowns
4. Aggregate the individual estimates to produce a **total cost of ownership (TCO)** that aligns with an APC estimate.

**Example conversation**:
> *"I need an estimate for a 3-tier web app in East US: 2× D4s_v3 VMs running 24/7, a Standard_S1 SQL Database, and Premium blob storage. Apply our 15% enterprise discount. Format it like an Azure Pricing Calculator export."*

The AI assistant will call `azure_cost_estimate` for each line item and present a consolidated table with per-service and total costs, matching the structure of an APC estimate.

### Import a Set of Services (Bulk Pricing)

Price an entire architecture or service portfolio in a single conversational exchange.

**Workflow**:
1. Provide a list of services, SKUs, regions, and usage patterns (as a table, JSON, or natural language).
2. The AI assistant calls the appropriate tools for each line item.
3. Results are aggregated into a unified pricing report.

**Example input** (natural language):
> *"Get pricing for these services in eastus:*
> - *2× Standard_D4s_v3 VMs, 730 hrs/month*
> - *1× Azure SQL Database S3, 730 hrs/month*
> - *500 GB Premium SSD managed disk*
> - *Azure Kubernetes Service with 3 D2s_v3 nodes*
> *Apply a 10% discount to everything."*

**Example input** (structured):
```json
[
  { "service": "Virtual Machines", "sku": "D4s_v3", "region": "eastus", "hours": 730, "qty": 2 },
  { "service": "Azure SQL Database", "sku": "S3", "region": "eastus", "hours": 730, "qty": 1 },
  { "service": "Storage", "sku": "Premium SSD", "region": "eastus" },
  { "service": "Azure Kubernetes Service", "sku": "D2s_v3", "region": "eastus", "hours": 730, "qty": 3 }
]
```

### Architecture Cost Modelling

Model the cost of a complete cloud architecture by combining multiple tool calls:

1. **Discovery phase**: Use `azure_sku_discovery` to identify the right SKUs for each tier (compute, database, storage, networking).
2. **Pricing phase**: Use `azure_cost_estimate` for each component.
3. **Comparison phase**: Use `azure_price_compare` to evaluate alternative regions or SKU sizes.
4. **Optimisation phase**: Review savings plans and reserved instance pricing to find the lowest-cost commitment strategy.

### Budget Forecasting

Build forward-looking cost projections:

- Use `azure_cost_estimate` with different `hours_per_month` values to model growth scenarios.
- Compare on-demand vs. savings plan pricing to quantify commitment savings over 1 and 3 years.
- Apply discount percentages to model negotiated enterprise rates.
- Multiply results by expected instance counts for fleet-level forecasting.

### Cost Optimization Analysis

Identify savings opportunities across your Azure footprint:

1. **Region arbitrage**: Use `azure_price_compare` across all target regions to find the cheapest deployment location.
2. **Right-sizing**: Use `azure_discover_skus` to find cheaper SKU alternatives within the same service family.
3. **Commitment analysis**: Compare on-demand vs. 1-year vs. 3-year savings plans in `azure_cost_estimate` output.
4. **Discount stacking**: Layer customer discounts on top of savings plans to see the maximum potential savings.

---

## API Integration Details

| Property | Value |
|---|---|
| **Base URL** | `https://prices.azure.com/api/retail/prices` |
| **API Version** | `2023-01-01-preview` |
| **Authentication** | None (public API) |
| **Max results per request** | 1,000 |
| **Rate limit handling** | Automatic retry with exponential backoff (5s, 10s, 15s) |
| **Max retries** | 3 (4 total attempts) |
| **Response format** | JSON with `Items` array and `NextPageLink` for pagination |

---

## Filtering & Query Language

The server builds [OData](https://www.odata.org/) `$filter` expressions from the tool parameters:

| Parameter | OData Expression |
|---|---|
| `service_name` | `serviceName eq '{value}'` |
| `service_family` | `serviceFamily eq '{value}'` |
| `region` | `armRegionName eq '{value}'` |
| `sku_name` | `contains(skuName, '{value}')` |
| `price_type` | `priceType eq '{value}'` |

Multiple filters are joined with `and`. The `sku_name` filter uses `contains()` for partial matching; all others use exact `eq` matching.

---

## Error Handling & Resilience

| Scenario | Behaviour |
|---|---|
| **HTTP 429 (rate limited)** | Retries up to 3 times with increasing backoff (5s → 10s → 15s) |
| **Network errors** | Caught and returned as user-friendly error messages |
| **SKU not found** | Suggests up to 5 similar SKUs with pricing (when `validate_sku` is enabled) |
| **Service not found** | Falls back to fuzzy matching and suggests up to 5 alternative services |
| **No results** | Returns an empty result set with filter details for debugging |
| **Unexpected exceptions** | Caught at the tool handler level and returned as error text |

---

## Supported Azure Services (Aliases)

The fuzzy matching engine supports these natural-language aliases out of the box:

| Category | Aliases → Azure Service |
|---|---|
| **Compute** | `vm`, `vms`, `virtual machine`, `compute` → Virtual Machines |
| **Web** | `app service`, `app services`, `web app`, `web apps`, `websites`, `web service` → Azure App Service |
| **Databases** | `sql`, `sql database`, `database`, `sql server` → Azure SQL Database |
| **NoSQL** | `cosmos`, `cosmosdb`, `cosmos db`, `document db` → Azure Cosmos DB |
| **Containers** | `kubernetes`, `aks`, `k8s`, `container service` → Azure Kubernetes Service |
| **Serverless** | `functions`, `function app`, `serverless` → Azure Functions |
| **Caching** | `redis`, `cache` → Azure Cache for Redis |
| **AI** | `ai`, `cognitive`, `cognitive services` → Azure AI services |
| **AI (OpenAI)** | `openai` → Azure OpenAI |
| **Storage** | `storage`, `blob`, `blob storage`, `file storage`, `disk` → Storage |
| **Networking** | `networking`, `network`, `vnet` → Virtual Network |
| **Load Balancing** | `load balancer`, `lb` → Load Balancer |
| **App Gateway** | `application gateway`, `app gateway` → Application Gateway |

---

## Configuration & Deployment

### Claude Desktop

Add to `claude_desktop_config.json`:

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

### VS Code (GitHub Copilot)

Add to VS Code `settings.json`:

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
  },
  "chat.mcp.discovery.enabled": true
}
```

### Dependencies

| Package | Minimum Version | Purpose |
|---|---|---|
| `mcp` | 1.0.0 | Model Context Protocol SDK |
| `aiohttp` | 3.9.0 | Async HTTP client for Azure API |
| `pydantic` | 2.0.0 | Data validation and schema |
| `requests` | 2.31.0 | HTTP utilities (legacy) |

### Runtime Requirements

- **Python**: 3.8+
- **OS**: Windows, macOS, Linux
- **Network**: Outbound HTTPS to `prices.azure.com`
- **Authentication**: None required

---

## Limitations & Known Constraints

| Limitation | Detail |
|---|---|
| **Pagination** | The server fetches a single page of results per query (up to 1,000 items). Deep result sets beyond the first page are not automatically traversed. |
| **Price types** | Only `Consumption`, `Reservation`, and `DevTestConsumption` are directly filterable. |
| **Savings plan availability** | Savings plan data depends on the Azure API; not all SKUs include savings plan pricing. |
| **Discount model** | Currently uses a static 10% default discount. No integration with an external discount/contract database. |
| **No caching** | Every tool call makes a live API request. There is no local price cache for offline or faster repeated queries. |
| **OData filter limitations** | Service names are case-sensitive in `eq` filters. Use `azure_sku_discovery` for case-insensitive fuzzy matching. |
| **Single-page results** | `NextPageLink` is detected but not automatically followed. Very broad queries may be incomplete. |

---

*Built with the [Model Context Protocol](https://modelcontextprotocol.io/) for seamless integration with AI assistants.*
