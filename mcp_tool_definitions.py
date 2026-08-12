"""Dependency-free MCP tool metadata for fast server startup."""

TOOLS = [
    {
        "name": "azure_price_search",
        "description": "Search Azure retail prices with various filters",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Azure service name (e.g., 'Virtual Machines', 'Storage')"},
                "service_family": {"type": "string", "description": "Service family (e.g., 'Compute', 'Storage', 'Networking')"},
                "region": {"type": "string", "description": "Azure region (e.g., 'eastus', 'westeurope')"},
                "sku_name": {"type": "string", "description": "SKU name to search for (partial matches supported)"},
                "price_type": {"type": "string", "description": "Price type: 'Consumption', 'Reservation', or 'DevTestConsumption'"},
                "currency_code": {"type": "string", "description": "Currency code (default: USD)", "default": "USD"},
                "limit": {"type": "integer", "description": "Maximum number of results (default: 50)", "default": 50},
                "discount_percentage": {"type": "number", "description": "Discount percentage to apply to prices (e.g., 10 for 10% discount)"},
                "validate_sku": {"type": "boolean", "description": "Whether to validate SKU names and provide suggestions (default: true)", "default": True},
            },
        },
    },
    {
        "name": "azure_price_compare",
        "description": "Compare Azure prices across regions or SKUs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Azure service name to compare"},
                "sku_name": {"type": "string", "description": "Specific SKU to compare (optional)"},
                "regions": {"type": "array", "items": {"type": "string"}, "description": "List of regions to compare (if not provided, compares SKUs)"},
                "currency_code": {"type": "string", "description": "Currency code (default: USD)", "default": "USD"},
                "discount_percentage": {"type": "number", "description": "Discount percentage to apply to prices (e.g., 10 for 10% discount)"},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "azure_cost_estimate",
        "description": "Estimate Azure costs based on usage patterns",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Azure service name"},
                "sku_name": {"type": "string", "description": "SKU name"},
                "region": {"type": "string", "description": "Azure region"},
                "hours_per_month": {"type": "number", "description": "Expected hours of usage per month (default: 730 for full month)", "default": 730},
                "currency_code": {"type": "string", "description": "Currency code (default: USD)", "default": "USD"},
                "discount_percentage": {"type": "number", "description": "Discount percentage to apply to prices (e.g., 10 for 10% discount)"},
            },
            "required": ["service_name", "sku_name", "region"],
        },
    },
    {
        "name": "azure_discover_skus",
        "description": "Discover available SKUs for a specific Azure service",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Azure service name"},
                "region": {"type": "string", "description": "Azure region (optional)"},
                "price_type": {"type": "string", "description": "Price type (default: 'Consumption')", "default": "Consumption"},
                "limit": {"type": "integer", "description": "Maximum number of SKUs to return (default: 100)", "default": 100},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "azure_sku_discovery",
        "description": "Discover available SKUs for Azure services with intelligent name matching",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_hint": {"type": "string", "description": "Service name or description (e.g., 'app service', 'web app', 'vm', 'storage'). Supports fuzzy matching."},
                "region": {"type": "string", "description": "Optional Azure region to filter results"},
                "currency_code": {"type": "string", "description": "Currency code (default: USD)", "default": "USD"},
                "limit": {"type": "integer", "description": "Maximum number of results (default: 30)", "default": 30},
            },
            "required": ["service_hint"],
        },
    },
    {
        "name": "get_customer_discount",
        "description": "Get customer discount information. All prices are retail by default \u2014 discounts are only applied when explicitly requested via discount_percentage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID (optional, defaults to 'default' customer)"},
            },
        },
    },
    {
        "name": "azure_service_discovery",
        "description": "Discover Azure services by scenario, category, or service family. Use when the user asks 'what services exist for AI?', 'show me database options', 'what networking services are available?', or any exploration query. Returns services grouped by category with aliases, tier info, and sample pricing. Call with no parameters to see the full service directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "description": "Scenario or use case to explore (e.g., 'ai', 'data', 'web application', 'iot', 'security', 'serverless', 'containers', 'devops', 'messaging', 'hybrid')"},
                "category": {"type": "string", "description": "Specific service category (e.g., 'AI & ML', 'Databases', 'Networking', 'Compute', 'Storage', 'Integration')"},
                "service_family": {"type": "string", "description": "Azure service family from the Retail Prices API (e.g., 'Compute', 'Databases', 'Analytics')"},
                "region": {"type": "string", "description": "Azure region for sample pricing (e.g., 'eastus', 'westeurope')"},
                "include_pricing": {"type": "boolean", "description": "Include sample pricing for each service (default: true, set false for faster results)", "default": True},
                "limit": {"type": "integer", "description": "Maximum number of services to return (default: 20)", "default": 20},
            },
        },
    },
]