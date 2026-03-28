#!/usr/bin/env python3
"""
Comprehensive validation test for Azure Pricing MCP Server.
Tests alias resolution, deprecated service warnings, and API connectivity.
Produces evidence output for review.
"""

import asyncio
import json
import sys
import time
from datetime import datetime

# Track results
results = {
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "python_version": sys.version,
    "tests": [],
    "summary": {"passed": 0, "failed": 0, "warnings": 0}
}

def record(test_name, status, detail=""):
    entry = {"test": test_name, "status": status, "detail": detail}
    results["tests"].append(entry)
    if status == "PASS":
        results["summary"]["passed"] += 1
    elif status == "FAIL":
        results["summary"]["failed"] += 1
    else:
        results["summary"]["warnings"] += 1
    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(status, "❓")
    print(f"  {icon} {test_name}: {status} {('- ' + detail) if detail else ''}")


async def run_tests():
    print("=" * 70)
    print("Azure Pricing MCP Server — Validation Test Suite")
    print("=" * 70)

    # --- Test 1: Module import ---
    print("\n📦 Test Group 1: Module Import")
    try:
        from azure_pricing_server import AzurePricingServer, server, main
        record("Import azure_pricing_server", "PASS")
    except Exception as e:
        record("Import azure_pricing_server", "FAIL", str(e))
        print("\n⛔ Cannot continue without module import.")
        return results

    # --- Test 2: Server instantiation ---
    print("\n🔧 Test Group 2: Server Instantiation")
    try:
        ps = AzurePricingServer()
        record("AzurePricingServer() instantiation", "PASS")
    except Exception as e:
        record("AzurePricingServer() instantiation", "FAIL", str(e))
        return results

    # --- Test 3: Active alias resolution (via _find_similar_services) ---
    print("\n🔍 Test Group 3: Active Service Alias Resolution")
    active_aliases = {
        "openai": "Foundry Models",
        "gpt-4": "Foundry Models",
        "speech": "Foundry Tools",
        "acs": "Voice Core",
        "container apps": "Azure Container Apps",
        "key vault": "Key Vault",
        "app service": "Azure App Service",
        "vm": "Virtual Machines",
        "sql": "SQL Database",
        "cosmos": "Azure Cosmos DB",
        "aks": "Azure Kubernetes Service",
        "ai search": "Azure Cognitive Search",
        "signalr": "SignalR",
        "apim": "API Management",
        "event grid": "Event Grid",
        "service bus": "Service Bus",
        "log analytics": "Log Analytics",
    }

    async with ps:
        for alias, expected in active_aliases.items():
            try:
                result = await ps._find_similar_services(service_name=alias, limit=5)
                used = result.get("suggestion_used", "")
                has_items = len(result.get("items", [])) > 0
                has_deprecation = "deprecation_warning" in result and result["deprecation_warning"]

                if used == expected and has_items and not has_deprecation:
                    record(f"Alias '{alias}' → '{expected}'", "PASS",
                           f"{len(result['items'])} items")
                elif used == expected and not has_items:
                    record(f"Alias '{alias}' → '{expected}'", "WARN",
                           "Mapped correctly but API returned 0 items (may be region/availability)")
                elif used != expected:
                    record(f"Alias '{alias}' → '{expected}'", "FAIL",
                           f"Got '{used}' instead")
                else:
                    record(f"Alias '{alias}' → '{expected}'", "PASS",
                           f"{len(result['items'])} items" + (" (has deprecation)" if has_deprecation else ""))
            except Exception as e:
                record(f"Alias '{alias}' → '{expected}'", "FAIL", str(e))

    # --- Test 4: Deprecated service warnings ---
    print("\n⚠️ Test Group 4: Deprecated Service Warnings")
    deprecated_aliases = {
        "luis": {"status": "retired", "replacement_contains": "CLU"},
        "qna maker": {"status": "retired", "replacement_contains": "Question Answering"},
        "personalizer": {"status": "retiring", "replacement_contains": "Azure"},
        "anomaly detector": {"status": "retiring", "replacement_contains": "Azure"},
        "content moderator": {"status": "deprecated", "replacement_contains": "Content Safety"},
        "form recognizer": {"status": "rebranded", "replacement_contains": "Document Intelligence"},
        "custom vision": {"status": "retiring", "replacement_contains": "Vision"},
        "metrics advisor": {"status": "retiring", "replacement_contains": "Azure"},
    }

    async with ps:
        for alias, checks in deprecated_aliases.items():
            try:
                result = await ps._find_similar_services(service_name=alias, limit=5)
                dw = result.get("deprecation_warning")
                if dw:
                    status_match = dw["status"] == checks["status"]
                    repl_match = checks["replacement_contains"].lower() in dw["replacement"].lower()
                    if status_match and repl_match:
                        record(f"Deprecated '{alias}' warning", "PASS",
                               f"status={dw['status']}, replacement={dw['replacement']}")
                    else:
                        record(f"Deprecated '{alias}' warning", "FAIL",
                               f"status_match={status_match}, repl_match={repl_match}")
                else:
                    record(f"Deprecated '{alias}' warning", "FAIL",
                           "No deprecation_warning in result")
            except Exception as e:
                record(f"Deprecated '{alias}' warning", "FAIL", str(e))

    # --- Test 5: Fuzzy/partial matching ---
    print("\n🔎 Test Group 5: Fuzzy / Partial Matching")
    fuzzy_tests = [
        ("virtual machine", "Virtual Machines"),
        ("storage", "Storage"),
        ("functions", "Functions"),
    ]

    async with ps:
        for term, expected_fragment in fuzzy_tests:
            try:
                result = await ps._find_similar_services(service_name=term, limit=5)
                used = result.get("suggestion_used", "")
                has_items = len(result.get("items", [])) > 0
                if expected_fragment.lower() in used.lower() and has_items:
                    record(f"Fuzzy '{term}' → '{used}'", "PASS",
                           f"{len(result['items'])} items")
                elif has_items:
                    record(f"Fuzzy '{term}' → '{used}'", "WARN",
                           f"Expected '{expected_fragment}' in mapping, got '{used}' ({len(result['items'])} items)")
                else:
                    record(f"Fuzzy '{term}'", "WARN",
                           f"No items returned (API may not have exact match)")
            except Exception as e:
                record(f"Fuzzy '{term}'", "FAIL", str(e))

    # --- Test 6: Direct API connectivity ---
    print("\n🌐 Test Group 6: API Connectivity")
    async with ps:
        try:
            result = await ps.search_azure_prices(
                service_name="Virtual Machines",
                currency_code="USD",
                limit=3
            )
            if result["items"]:
                record("Azure Pricing API direct call", "PASS",
                       f"Got {len(result['items'])} items")
            else:
                record("Azure Pricing API direct call", "WARN",
                       "No items returned")
        except Exception as e:
            record("Azure Pricing API direct call", "FAIL", str(e))

    # --- Test 7: discover_service_skus with deprecation passthrough ---
    print("\n🏗️ Test Group 7: SKU Discovery + Deprecation Passthrough")
    async with ps:
        try:
            result = await ps.discover_service_skus(
                service_hint="form recognizer",
                currency_code="USD",
                limit=5
            )
            dw = result.get("deprecation_warning")
            if dw and dw["status"] == "rebranded":
                record("SKU discovery deprecation passthrough", "PASS",
                       f"Warning: {dw['message'][:60]}...")
            elif dw:
                record("SKU discovery deprecation passthrough", "WARN",
                       f"Got warning but status={dw['status']}")
            else:
                record("SKU discovery deprecation passthrough", "FAIL",
                       "No deprecation_warning on SKU discovery result")
        except Exception as e:
            record("SKU discovery deprecation passthrough", "FAIL", str(e))

    # --- Test 8: Alias count / coverage ---
    print("\n📊 Test Group 8: Alias & Coverage Stats")
    import inspect
    src = inspect.getsource(ps._find_similar_services)
    active_count = src.count('": "')
    record(f"Active alias entries", "PASS", f"~{active_count} alias lines detected in source")

    # --- Summary ---
    print("\n" + "=" * 70)
    total = results["summary"]["passed"] + results["summary"]["failed"] + results["summary"]["warnings"]
    print(f"RESULTS: {total} tests — "
          f"✅ {results['summary']['passed']} passed, "
          f"❌ {results['summary']['failed']} failed, "
          f"⚠️ {results['summary']['warnings']} warnings")
    print("=" * 70)

    return results


def generate_evidence_markdown(results):
    """Generate evidence markdown from test results."""
    lines = []
    lines.append("# Azure Pricing MCP Server — Validation Evidence")
    lines.append("")
    lines.append(f"**Date:** {results['timestamp']}")
    lines.append(f"**Python:** {results['python_version'].split()[0]}")
    lines.append("")

    lines.append("## Summary")
    s = results["summary"]
    total = s["passed"] + s["failed"] + s["warnings"]
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Tests | {total} |")
    lines.append(f"| ✅ Passed | {s['passed']} |")
    lines.append(f"| ❌ Failed | {s['failed']} |")
    lines.append(f"| ⚠️ Warnings | {s['warnings']} |")
    lines.append("")

    # Group tests
    groups = {}
    current_group = "General"
    group_order = []
    for t in results["tests"]:
        tn = t["test"]
        if "Alias '" in tn and "Deprecated" not in tn:
            g = "Active Service Alias Resolution"
        elif "Deprecated" in tn:
            g = "Deprecated Service Warnings"
        elif "Fuzzy" in tn:
            g = "Fuzzy / Partial Matching"
        elif "API" in tn:
            g = "API Connectivity"
        elif "SKU" in tn:
            g = "SKU Discovery + Deprecation Passthrough"
        elif "alias" in tn.lower() or "coverage" in tn.lower():
            g = "Alias Coverage Stats"
        elif "Import" in tn or "instantiation" in tn:
            g = "Module Import & Setup"
        else:
            g = "Other"
        if g not in groups:
            groups[g] = []
            group_order.append(g)
        groups[g].append(t)

    lines.append("## Detailed Results")
    lines.append("")
    for g in group_order:
        lines.append(f"### {g}")
        lines.append("")
        lines.append("| Test | Status | Detail |")
        lines.append("|------|--------|--------|")
        for t in groups[g]:
            icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(t["status"], "❓")
            detail = t["detail"].replace("|", "\\|") if t["detail"] else ""
            lines.append(f"| {t['test']} | {icon} {t['status']} | {detail} |")
        lines.append("")

    lines.append("## Test Environment")
    lines.append("")
    lines.append(f"- **Python Version:** {results['python_version'].split()[0]}")
    lines.append(f"- **OS:** Windows")
    lines.append(f"- **API Endpoint:** https://prices.azure.com/api/retail/prices")
    lines.append(f"- **Transport:** stdio (MCP)")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    results = asyncio.run(run_tests())
    md = generate_evidence_markdown(results)

    evidence_path = "VALIDATION_EVIDENCE.md"
    with open(evidence_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\n📄 Evidence written to {evidence_path}")

    sys.exit(1 if results["summary"]["failed"] > 0 else 0)

