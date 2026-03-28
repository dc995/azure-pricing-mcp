#!/usr/bin/env python3
"""
Sync Catalog — Merges service_catalog.json into azure_services.db (SQLite).

Usage:
    python sync_catalog.py                  # Sync JSON → SQLite
    python sync_catalog.py --from-api       # Also discover services from Azure Retail Prices API
    python sync_catalog.py --dry-run        # Show what would change without writing
    python sync_catalog.py --report         # Print coverage gap report

The JSON file is the human-editable source of truth.
The SQLite DB is the runtime state store read by the MCP server.
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("sync_catalog")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "azure_services.db"
CATALOG_PATH = BASE_DIR / "service_catalog.json"
AZURE_API_URL = "https://prices.azure.com/api/retail/prices"
API_VERSION = "2023-01-01-preview"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS service_aliases (
    alias           TEXT PRIMARY KEY,
    service_name    TEXT NOT NULL,
    service_family  TEXT,
    category        TEXT,
    source          TEXT,
    source_date     TEXT,
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS deprecated_services (
    alias           TEXT PRIMARY KEY,
    service_name    TEXT NOT NULL,
    status          TEXT NOT NULL,
    retirement_date TEXT,
    replacement     TEXT,
    message         TEXT,
    source          TEXT,
    source_date     TEXT,
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sku_tiers (
    service_name    TEXT NOT NULL,
    tier_name       TEXT NOT NULL,
    unit_count      REAL NOT NULL,
    unit_name       TEXT,
    description     TEXT,
    api_sku_name    TEXT,
    api_unit        TEXT,
    source          TEXT,
    source_date     TEXT,
    updated_at      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (service_name, tier_name)
);

CREATE TABLE IF NOT EXISTS azure_services (
    service_name    TEXT PRIMARY KEY,
    service_family  TEXT,
    discovered_at   TEXT DEFAULT (datetime('now')),
    last_seen_at    TEXT DEFAULT (datetime('now')),
    is_active       INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action          TEXT,
    table_name      TEXT,
    key_value       TEXT,
    details         TEXT,
    synced_at       TEXT DEFAULT (datetime('now'))
);
"""


def ensure_schema(conn: sqlite3.Connection):
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def load_catalog(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _log_action(conn, action, table, key, details=""):
    conn.execute(
        "INSERT INTO sync_log (action, table_name, key_value, details) VALUES (?, ?, ?, ?)",
        (action, table, key, details),
    )


def sync_aliases(conn: sqlite3.Connection, catalog: dict, dry_run=False):
    """Upsert aliases from JSON; prune aliases removed from JSON."""
    entries = catalog.get("service_aliases", [])
    meta = catalog.get("_metadata", {})
    default_source = meta.get("default_source", "")
    default_source_date = meta.get("default_source_date", "")
    now = datetime.now(timezone.utc).isoformat()
    incoming_keys = set()
    added, updated, removed = 0, 0, 0

    for entry in entries:
        alias = entry["alias"].strip().lower()
        incoming_keys.add(alias)
        svc = entry["service_name"]
        cat = entry.get("category", "")
        fam = entry.get("service_family", "")
        source = entry.get("source", default_source)
        source_date = entry.get("source_date", default_source_date)

        existing = conn.execute(
            "SELECT service_name, category FROM service_aliases WHERE alias = ?",
            (alias,),
        ).fetchone()

        if existing is None:
            if not dry_run:
                conn.execute(
                    "INSERT INTO service_aliases (alias, service_name, service_family, category, source, source_date, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (alias, svc, fam, cat, source, source_date, now),
                )
                _log_action(conn, "added", "service_aliases", alias, f"→ {svc}")
            log.info("ADD  alias '%s' → '%s'", alias, svc)
            added += 1
        elif existing[0] != svc or existing[1] != cat:
            if not dry_run:
                conn.execute(
                    "UPDATE service_aliases SET service_name=?, service_family=?, category=?, source=?, source_date=?, updated_at=? WHERE alias=?",
                    (svc, fam, cat, source, source_date, now, alias),
                )
                _log_action(conn, "updated", "service_aliases", alias, f"→ {svc} (was {existing[0]})")
            log.info("UPD  alias '%s' → '%s' (was '%s')", alias, svc, existing[0])
            updated += 1

    # Prune aliases that were removed from JSON
    db_aliases = {
        row[0]
        for row in conn.execute("SELECT alias FROM service_aliases").fetchall()
    }
    stale = db_aliases - incoming_keys
    for alias in sorted(stale):
        if not dry_run:
            conn.execute("DELETE FROM service_aliases WHERE alias = ?", (alias,))
            _log_action(conn, "removed", "service_aliases", alias, "pruned — no longer in catalog JSON")
        log.info("DEL  alias '%s' (no longer in catalog)", alias)
        removed += 1

    return added, updated, removed


def sync_deprecated(conn: sqlite3.Connection, catalog: dict, dry_run=False):
    """Upsert deprecated service entries; prune removed ones."""
    entries = catalog.get("deprecated_services", [])
    now = datetime.now(timezone.utc).isoformat()
    incoming_keys = set()
    added, updated, removed = 0, 0, 0

    for entry in entries:
        alias = entry["alias"].strip().lower()
        incoming_keys.add(alias)

        existing = conn.execute(
            "SELECT status, retirement_date FROM deprecated_services WHERE alias = ?",
            (alias,),
        ).fetchone()

        if existing is None:
            if not dry_run:
                conn.execute(
                    "INSERT INTO deprecated_services (alias, service_name, status, retirement_date, replacement, message, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (alias, entry["service_name"], entry["status"], entry.get("retirement_date"), entry.get("replacement"), entry.get("message"), now),
                )
                _log_action(conn, "added", "deprecated_services", alias, entry["status"])
            log.info("ADD  deprecated '%s' [%s]", alias, entry["status"])
            added += 1
        elif existing[0] != entry["status"] or existing[1] != entry.get("retirement_date"):
            if not dry_run:
                conn.execute(
                    "UPDATE deprecated_services SET service_name=?, status=?, retirement_date=?, replacement=?, message=?, updated_at=? WHERE alias=?",
                    (entry["service_name"], entry["status"], entry.get("retirement_date"), entry.get("replacement"), entry.get("message"), now, alias),
                )
                _log_action(conn, "updated", "deprecated_services", alias, f"status: {entry['status']}")
            log.info("UPD  deprecated '%s' → %s", alias, entry["status"])
            updated += 1

    db_aliases = {
        row[0]
        for row in conn.execute("SELECT alias FROM deprecated_services").fetchall()
    }
    stale = db_aliases - incoming_keys
    for alias in sorted(stale):
        if not dry_run:
            conn.execute("DELETE FROM deprecated_services WHERE alias = ?", (alias,))
            _log_action(conn, "removed", "deprecated_services", alias, "pruned")
        log.info("DEL  deprecated '%s'", alias)
        removed += 1

    return added, updated, removed


def sync_sku_tiers(conn: sqlite3.Connection, catalog: dict, dry_run=False):
    """Upsert SKU tier mappings from JSON; prune removed ones."""
    entries = catalog.get("sku_tiers", [])
    now = datetime.now(timezone.utc).isoformat()
    incoming_keys = set()
    added, updated, removed = 0, 0, 0

    for svc_entry in entries:
        svc_name = svc_entry["service_name"]
        unit_name = svc_entry.get("unit_name", "")
        api_sku = svc_entry.get("api_sku_name")
        api_unit = svc_entry.get("api_unit", "")
        source = svc_entry.get("source", "")
        source_date = svc_entry.get("source_date", "")

        for tier in svc_entry.get("tiers", []):
            tier_name = tier["name"]
            key = (svc_name, tier_name)
            incoming_keys.add(key)
            unit_count = tier["units"]
            desc = tier.get("description", "")

            existing = conn.execute(
                "SELECT unit_count FROM sku_tiers WHERE service_name = ? AND tier_name = ?",
                (svc_name, tier_name),
            ).fetchone()

            if existing is None:
                if not dry_run:
                    conn.execute(
                        "INSERT INTO sku_tiers (service_name, tier_name, unit_count, unit_name, description, api_sku_name, api_unit, source, source_date, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (svc_name, tier_name, unit_count, unit_name, desc, api_sku, api_unit, source, source_date, now),
                    )
                    _log_action(conn, "added", "sku_tiers", f"{svc_name}/{tier_name}", f"{unit_count} {unit_name}")
                log.info("ADD  tier '%s/%s' = %s %s", svc_name, tier_name, unit_count, unit_name)
                added += 1
            elif existing[0] != unit_count:
                if not dry_run:
                    conn.execute(
                        "UPDATE sku_tiers SET unit_count=?, unit_name=?, description=?, api_sku_name=?, api_unit=?, source=?, source_date=?, updated_at=? WHERE service_name=? AND tier_name=?",
                        (unit_count, unit_name, desc, api_sku, api_unit, source, source_date, now, svc_name, tier_name),
                    )
                    _log_action(conn, "updated", "sku_tiers", f"{svc_name}/{tier_name}", f"{unit_count} (was {existing[0]})")
                log.info("UPD  tier '%s/%s' = %s (was %s)", svc_name, tier_name, unit_count, existing[0])
                updated += 1

    # Prune tiers removed from JSON
    db_tiers = {
        (row[0], row[1])
        for row in conn.execute("SELECT service_name, tier_name FROM sku_tiers").fetchall()
    }
    stale = db_tiers - incoming_keys
    for svc_name, tier_name in sorted(stale):
        if not dry_run:
            conn.execute("DELETE FROM sku_tiers WHERE service_name = ? AND tier_name = ?", (svc_name, tier_name))
            _log_action(conn, "removed", "sku_tiers", f"{svc_name}/{tier_name}", "pruned")
        log.info("DEL  tier '%s/%s'", svc_name, tier_name)
        removed += 1

    return added, updated, removed


def discover_from_api(conn: sqlite3.Connection, dry_run=False, max_pages=10):
    """Query Azure Retail Prices API to discover all known service names."""
    if requests is None:
        log.error("'requests' package required for --from-api. Install with: pip install requests")
        return 0

    SERVICE_FAMILIES = [
        "Analytics", "Azure Arc", "Azure Communication Services", "Azure Security",
        "Azure Stack", "Compute", "Containers", "Data", "Databases",
        "Developer Tools", "Dynamics", "Gaming", "Integration",
        "Internet of Things", "Management and Governance", "Microsoft Syntex",
        "Mixed Reality", "Networking", "Other", "Power Platform",
        "Quantum Computing", "Security", "Storage", "Telecommunications",
        "Web", "Windows Virtual Desktop",
    ]

    now = datetime.now(timezone.utc).isoformat()
    discovered = 0

    for family in SERVICE_FAMILIES:
        log.info("Scanning family: %s", family)
        params = {
            "api-version": API_VERSION,
            "$filter": f"serviceFamily eq '{family}'",
        }
        try:
            page = 0
            next_url = AZURE_API_URL
            next_params = params
            while next_url and page < max_pages:
                resp = requests.get(next_url, params=next_params, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("Items", []):
                    svc = item.get("serviceName", "")
                    sf = item.get("serviceFamily", "")
                    if not svc:
                        continue
                    existing = conn.execute(
                        "SELECT last_seen_at FROM azure_services WHERE service_name = ?",
                        (svc,),
                    ).fetchone()
                    if existing is None:
                        if not dry_run:
                            conn.execute(
                                "INSERT INTO azure_services (service_name, service_family, discovered_at, last_seen_at, is_active) VALUES (?, ?, ?, ?, 1)",
                                (svc, sf, now, now),
                            )
                            _log_action(conn, "api_discovered", "azure_services", svc, f"family={sf}")
                        log.info("DISCOVERED  '%s' [%s]", svc, sf)
                        discovered += 1
                    else:
                        if not dry_run:
                            conn.execute(
                                "UPDATE azure_services SET last_seen_at=?, is_active=1 WHERE service_name=?",
                                (now, svc),
                            )
                next_url = data.get("NextPageLink")
                next_params = None  # NextPageLink includes params
                page += 1
        except Exception as e:
            log.warning("Error scanning family '%s': %s", family, e)

    return discovered


def print_report(conn: sqlite3.Connection):
    """Print coverage gap report: API-known services vs alias coverage."""
    api_services = conn.execute(
        "SELECT service_name, service_family FROM azure_services WHERE is_active = 1 ORDER BY service_family, service_name"
    ).fetchall()

    if not api_services:
        log.warning("No API-discovered services in DB. Run with --from-api first.")
        return

    aliased_targets = {
        row[0]
        for row in conn.execute("SELECT DISTINCT service_name FROM service_aliases").fetchall()
    }

    covered = []
    gaps = []
    for svc, fam in api_services:
        if svc in aliased_targets:
            covered.append((svc, fam))
        else:
            gaps.append((svc, fam))

    total = len(api_services)
    print(f"\n{'='*70}")
    print(f"AZURE SERVICE COVERAGE REPORT")
    print(f"{'='*70}")
    print(f"API-known services:  {total}")
    print(f"Covered by aliases:  {len(covered)}  ({len(covered)*100//total}%)")
    print(f"GAPS (no aliases):   {len(gaps)}  ({len(gaps)*100//total}%)")
    print(f"{'='*70}")

    if gaps:
        print(f"\nUNCOVERED SERVICES (sorted by family):")
        print(f"{'-'*70}")
        current_fam = None
        for svc, fam in gaps:
            if fam != current_fam:
                current_fam = fam
                print(f"\n  [{fam}]")
            print(f"    • {svc}")

    print(f"\nCOVERED SERVICES ({len(covered)}):")
    print(f"{'-'*70}")
    current_fam = None
    for svc, fam in covered:
        if fam != current_fam:
            current_fam = fam
            print(f"\n  [{fam}]")
        print(f"    ✓ {svc}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Sync service_catalog.json → azure_services.db")
    parser.add_argument("--from-api", action="store_true", help="Also discover services from Azure Retail Prices API")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing to DB")
    parser.add_argument("--report", action="store_true", help="Print coverage gap report")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Path to SQLite database")
    parser.add_argument("--catalog", type=str, default=str(CATALOG_PATH), help="Path to service_catalog.json")
    parser.add_argument("--api-pages", type=int, default=10, help="Max API pages per family (default: 10)")
    args = parser.parse_args()

    db_path = Path(args.db)
    catalog_path = Path(args.catalog)

    if not catalog_path.exists():
        log.error("Catalog file not found: %s", catalog_path)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_schema(conn)

    catalog = load_catalog(catalog_path)
    mode = "DRY RUN" if args.dry_run else "LIVE"
    log.info("=== Sync started [%s] ===", mode)
    log.info("Catalog: %s", catalog_path)
    log.info("Database: %s", db_path)

    a_add, a_upd, a_del = sync_aliases(conn, catalog, dry_run=args.dry_run)
    d_add, d_upd, d_del = sync_deprecated(conn, catalog, dry_run=args.dry_run)
    t_add, t_upd, t_del = sync_sku_tiers(conn, catalog, dry_run=args.dry_run)

    if not args.dry_run:
        conn.commit()

    log.info("Aliases:     +%d  ~%d  -%d", a_add, a_upd, a_del)
    log.info("Deprecated:  +%d  ~%d  -%d", d_add, d_upd, d_del)
    log.info("SKU Tiers:   +%d  ~%d  -%d", t_add, t_upd, t_del)

    if args.from_api:
        log.info("=== API Discovery ===")
        discovered = discover_from_api(conn, dry_run=args.dry_run, max_pages=args.api_pages)
        if not args.dry_run:
            conn.commit()
        log.info("API discovered: %d new services", discovered)

    if args.report:
        print_report(conn)

    conn.close()
    log.info("=== Sync complete ===")


if __name__ == "__main__":
    main()
