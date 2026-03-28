# Azure Pricing MCP Server — Validation Evidence

**Date:** 2026-03-12T17:53:29.388357Z
**Python:** 3.12.10

## Summary
| Metric | Count |
|--------|-------|
| Total Tests | 33 |
| ✅ Passed | 32 |
| ❌ Failed | 0 |
| ⚠️ Warnings | 1 |

## Detailed Results

### Module Import & Setup

| Test | Status | Detail |
|------|--------|--------|
| Import azure_pricing_server | ✅ PASS |  |
| AzurePricingServer() instantiation | ✅ PASS |  |

### Active Service Alias Resolution

| Test | Status | Detail |
|------|--------|--------|
| Alias 'openai' → 'Foundry Models' | ✅ PASS | 5 items |
| Alias 'gpt-4' → 'Foundry Models' | ✅ PASS | 5 items |
| Alias 'speech' → 'Foundry Tools' | ✅ PASS | 5 items |
| Alias 'acs' → 'Voice Core' | ✅ PASS | 5 items |
| Alias 'container apps' → 'Azure Container Apps' | ✅ PASS | 5 items |
| Alias 'key vault' → 'Key Vault' | ✅ PASS | 5 items |
| Alias 'app service' → 'Azure App Service' | ✅ PASS | 5 items |
| Alias 'vm' → 'Virtual Machines' | ✅ PASS | 5 items |
| Alias 'sql' → 'SQL Database' | ✅ PASS | 5 items |
| Alias 'cosmos' → 'Azure Cosmos DB' | ✅ PASS | 5 items |
| Alias 'aks' → 'Azure Kubernetes Service' | ✅ PASS | 5 items |
| Alias 'ai search' → 'Azure Cognitive Search' | ✅ PASS | 5 items |
| Alias 'signalr' → 'SignalR' | ✅ PASS | 5 items |
| Alias 'apim' → 'API Management' | ✅ PASS | 5 items |
| Alias 'event grid' → 'Event Grid' | ✅ PASS | 5 items |
| Alias 'service bus' → 'Service Bus' | ✅ PASS | 5 items |
| Alias 'log analytics' → 'Log Analytics' | ✅ PASS | 5 items |

### Deprecated Service Warnings

| Test | Status | Detail |
|------|--------|--------|
| Deprecated 'luis' warning | ✅ PASS | status=retired, replacement=Conversational Language Understanding / CLU (Azure AI Language) |
| Deprecated 'qna maker' warning | ✅ PASS | status=retired, replacement=Custom Question Answering (Azure AI Language) |
| Deprecated 'personalizer' warning | ✅ PASS | status=retiring, replacement=Azure AI services or Azure Machine Learning |
| Deprecated 'anomaly detector' warning | ✅ PASS | status=retiring, replacement=Azure AI services or Azure Machine Learning |
| Deprecated 'content moderator' warning | ✅ PASS | status=deprecated, replacement=Azure AI Content Safety |
| Deprecated 'form recognizer' warning | ✅ PASS | status=rebranded, replacement=Azure AI Document Intelligence |
| Deprecated 'custom vision' warning | ✅ PASS | status=retiring, replacement=Azure AI Vision (GA) or Azure Machine Learning |
| Deprecated 'metrics advisor' warning | ✅ PASS | status=retiring, replacement=Azure Monitor or Azure Machine Learning |

### Fuzzy / Partial Matching

| Test | Status | Detail |
|------|--------|--------|
| Fuzzy 'virtual machine' → 'Virtual Machines' | ✅ PASS | 5 items |
| Fuzzy 'storage' → 'Storage' | ✅ PASS | 5 items |
| Fuzzy 'functions' | ⚠️ WARN | No items returned (API may not have exact match) |

### API Connectivity

| Test | Status | Detail |
|------|--------|--------|
| Azure Pricing API direct call | ✅ PASS | Got 3 items |

### SKU Discovery + Deprecation Passthrough

| Test | Status | Detail |
|------|--------|--------|
| SKU discovery deprecation passthrough | ✅ PASS | Warning: 🔄 Form Recognizer has been rebranded to Azure AI Document In... |

### Alias Coverage Stats

| Test | Status | Detail |
|------|--------|--------|
| Active alias entries | ✅ PASS | ~220 alias lines detected in source |

## Test Environment

- **Python Version:** 3.12.10
- **OS:** Windows
- **API Endpoint:** https://prices.azure.com/api/retail/prices
- **Transport:** stdio (MCP)
