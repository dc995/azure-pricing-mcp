# Azure Service Coverage Gap Log

> Generated: 2026-03-20 | Coverage: **156/156 services (100%)**
> Source: Azure Retail Prices API (`2023-01-01-preview`)

## Coverage Summary

| Status | Count | % |
|--------|-------|---|
| Covered by aliases | 156 | 100% |
| Remaining gaps | 0 | 0% |
| Total API services | 156 | 100% |

## Remaining Gaps (0 services)

All 156 API-discovered services now have at least one alias.

### Previously Uncovered — Now Resolved
All 45 previously uncovered services were added in the full backlog pass, including niche,
legacy, sub-services, and specialized services.

### Low Priority — Niche / Sub-services / Legacy
These are either sub-components of covered services, legacy, or very specialized:

| Service | Family | Reason |
|---------|--------|--------|
| SMS, Voice, Email, Messaging, Phone Numbers, Routing, Network Traversal | Azure Communication Services | Sub-services of Voice Core (already covered) |
| Azure Data Factory (v1) | Analytics | Superseded by v2 (already covered) |
| Power BI (standalone) | Analytics | Power BI Embedded already covered |
| Virtual Machines Licenses | Compute | License add-on, not standalone service |
| AKS on Azure Stack HCI | Containers | Niche hybrid variant |
| Azure Arc-enabled AKS | Containers | Niche hybrid variant |
| SQL Server Stretch Database | Databases | Legacy/deprecated feature |
| BizTalk Services | Integration | Legacy — replaced by Logic Apps |
| GitHub, GitHub AE | Developer Tools | Not Azure infrastructure |
| Visual Studio Codespaces | Developer Tools | Discontinued |
| Visual Studio Subscription | Developer Tools | Licensing, not infrastructure |
| Scheduler | Management | Legacy — replaced by Logic Apps |
| Insight and Analytics | Management | Legacy OMS service |
| Dynamics 365 for Customer Insights | Management | Dynamics product, not core Azure |
| Azure Active Directory B2C | Security | Legacy name — Microsoft Entra alias covers the replacement |
| Azure Active Directory for External Identities | Security | Legacy name — covered by Microsoft Entra |
| SAP Embrace | Other | SAP partnership product |
| Energy Data Manager | Other | Industry-specific |
| MS Bing Services | Other | Consumer service |

### Medium Priority — Worth Adding
| Service | Family | Suggested Aliases |
|---------|--------|-------------------|
| Firmware Analysis | Azure Arc | `firmware analysis` |
| Azure Orbital Edge | Azure Stack | `orbital edge` |
| Microsoft Planetary Computer Pro | Data | `planetary computer` |
| Azure Arc Enabled Databases | Databases | `arc databases` |
| Azure App Testing | Developer Tools | `app testing` |
| Azure Fluid Relay | Developer Tools | `fluid relay` |
| Test Base | Developer Tools | `test base` |
| AKS Edge Essentials | IoT | `aks edge` |
| Azure Device Registry | IoT | `device registry` |
| Azure Policy | Management | `policy`, `azure policy` |
| Change Tracking and Inventory | Management | `change tracking` |
| Azure Update Manager | Management | `update manager` |
| Advanced Container Networking Services | Networking | `container networking` |
| Azure Firewall Manager | Networking | `firewall manager` |
| Azure Orbital | Networking | `orbital`, `satellite` |
| Private Mobile Network | Networking | `private 5g`, `mobile network` |
| AI Ops | Telecommunications | `ai ops`, `telecom ai` |
| Azure Operator Nexus | Telecommunications | `operator nexus` |
| Packet Core | Telecommunications | `packet core`, `5g core` |
| Community Training | Web | `community training` |

## Limitations Preventing Full Coverage

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **API pagination** | Server fetches max 1000 items per query; very broad queries may miss results | Increase `--api-pages` in sync_catalog.py; use family-scoped queries |
| **API rate limiting** | 429 errors during bulk discovery (e.g., Microsoft Syntex family failed) | sync_catalog.py uses retry logic; re-run to catch missed families |
| **Service name case sensitivity** | `2023-01-01-preview` requires exact case matching for filters | SQLite aliases are case-insensitive; server lowercases user input |
| **Sub-service granularity** | Azure Communication Services has 7 sub-services (SMS, Voice, etc.) but APC treats them as one | Map common terms to parent; sub-services still accessible by exact name |
| **Rebranded services** | Some API names are stale (e.g., "Azure Cognitive Search" for "Azure AI Search") | Deprecated entries in catalog warn users and redirect |
| **Non-infrastructure services** | GitHub, Visual Studio, Dynamics 365 appear in API but aren't core Azure infra | Excluded from alias priority; still discoverable via exact name |
| **No new API version** | `2023-01-01-preview` is the only version as of 2026 | Monitor Microsoft Learn docs for updates |
| **Static discount model** | Default 10% discount is hardcoded; no integration with contract/EA pricing | Extensible via `get_customer_discount` tool |
| **Single-page results** | `NextPageLink` detected but not followed for deep queries | Could add auto-pagination in future |
