"""
Tests for the service catalog sync pipeline and SQLite-backed server loading.

Covers:
  - service_catalog.json schema and data integrity
  - sync_catalog.py idempotency, upsert, prune, and logging
  - azure_services.db schema correctness
  - AzurePricingServer loading aliases and deprecated entries from SQLite
  - Alias lookup correctness (exact, partial, deprecated)
  - Full coverage validation against API-discovered services
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = BASE_DIR / "service_catalog.json"
DB_PATH = BASE_DIR / "azure_services.db"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def catalog():
    """Load the service catalog JSON once for all tests."""
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite DB using sync_catalog.py for isolated tests."""
    db_file = tmp_path / "test_services.db"
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "sync_catalog.py"),
         "--db", str(db_file), "--catalog", str(CATALOG_PATH)],
        capture_output=True, text=True, cwd=str(BASE_DIR),
    )
    assert result.returncode == 0, f"sync_catalog.py failed:\n{result.stderr}"
    return db_file


@pytest.fixture
def tmp_db_conn(tmp_db):
    """Provide a connection to the temporary DB."""
    conn = sqlite3.connect(str(tmp_db))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ===========================================================================
# 1. JSON Catalog Schema & Integrity
# ===========================================================================

class TestCatalogJSON:
    """Validate service_catalog.json structure and data quality."""

    def test_catalog_file_exists(self):
        assert CATALOG_PATH.exists(), "service_catalog.json not found"

    def test_catalog_is_valid_json(self, catalog):
        assert isinstance(catalog, dict)

    def test_has_metadata(self, catalog):
        assert "_metadata" in catalog
        meta = catalog["_metadata"]
        assert "schema_version" in meta
        assert "last_updated" in meta

    def test_has_service_aliases_array(self, catalog):
        assert "service_aliases" in catalog
        assert isinstance(catalog["service_aliases"], list)
        assert len(catalog["service_aliases"]) > 0

    def test_has_deprecated_services_array(self, catalog):
        assert "deprecated_services" in catalog
        assert isinstance(catalog["deprecated_services"], list)

    def test_alias_entries_have_required_fields(self, catalog):
        for i, entry in enumerate(catalog["service_aliases"]):
            assert "alias" in entry, f"Entry {i} missing 'alias'"
            assert "service_name" in entry, f"Entry {i} missing 'service_name'"
            assert isinstance(entry["alias"], str) and len(entry["alias"]) > 0, \
                f"Entry {i}: alias must be a non-empty string"
            assert isinstance(entry["service_name"], str) and len(entry["service_name"]) > 0, \
                f"Entry {i}: service_name must be a non-empty string"

    def test_aliases_are_lowercase(self, catalog):
        for entry in catalog["service_aliases"]:
            assert entry["alias"] == entry["alias"].lower(), \
                f"Alias '{entry['alias']}' is not lowercase"

    def test_no_duplicate_aliases(self, catalog):
        aliases = [e["alias"] for e in catalog["service_aliases"]]
        dupes = [a for a in aliases if aliases.count(a) > 1]
        assert len(dupes) == 0, f"Duplicate aliases: {set(dupes)}"

    def test_deprecated_entries_have_required_fields(self, catalog):
        required = ["alias", "service_name", "status", "replacement", "message"]
        for i, entry in enumerate(catalog["deprecated_services"]):
            for field in required:
                assert field in entry, f"Deprecated entry {i} missing '{field}'"

    def test_deprecated_status_values_are_valid(self, catalog):
        valid_statuses = {"retired", "retiring", "deprecated", "rebranded"}
        for entry in catalog["deprecated_services"]:
            assert entry["status"] in valid_statuses, \
                f"Invalid status '{entry['status']}' for '{entry['alias']}'"

    def test_no_overlap_between_aliases_and_deprecated(self, catalog):
        alias_keys = {e["alias"] for e in catalog["service_aliases"]}
        deprecated_keys = {e["alias"] for e in catalog["deprecated_services"]}
        overlap = alias_keys & deprecated_keys
        assert len(overlap) == 0, f"Aliases overlap with deprecated: {overlap}"


# ===========================================================================
# 2. sync_catalog.py Behavior
# ===========================================================================

class TestSyncCatalog:
    """Test the sync utility's upsert, prune, and idempotency."""

    def test_sync_creates_db(self, tmp_db):
        assert tmp_db.exists(), "sync_catalog.py did not create the DB"
        assert tmp_db.stat().st_size > 0, "DB file is empty"

    def test_sync_creates_all_tables(self, tmp_db_conn):
        tables = {row[0] for row in tmp_db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        expected = {"service_aliases", "deprecated_services", "azure_services", "sync_log"}
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_sync_populates_aliases(self, tmp_db_conn, catalog):
        count = tmp_db_conn.execute("SELECT COUNT(*) FROM service_aliases").fetchone()[0]
        expected = len(catalog["service_aliases"])
        assert count == expected, f"Expected {expected} aliases, got {count}"

    def test_sync_populates_deprecated(self, tmp_db_conn, catalog):
        count = tmp_db_conn.execute("SELECT COUNT(*) FROM deprecated_services").fetchone()[0]
        expected = len(catalog["deprecated_services"])
        assert count == expected, f"Expected {expected} deprecated, got {count}"

    def test_sync_is_idempotent(self, tmp_db):
        """Running sync twice should produce no changes."""
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "sync_catalog.py"),
             "--db", str(tmp_db), "--catalog", str(CATALOG_PATH)],
            capture_output=True, text=True, cwd=str(BASE_DIR),
        )
        assert result.returncode == 0
        assert "+0  ~0  -0" in result.stderr, \
            f"Second sync was not idempotent:\n{result.stderr}"

    def test_sync_logs_initial_additions(self, tmp_db_conn):
        logs = tmp_db_conn.execute(
            "SELECT COUNT(*) FROM sync_log WHERE action = 'added'"
        ).fetchone()[0]
        assert logs > 0, "No 'added' entries in sync_log"

    def test_sync_prunes_removed_aliases(self, tmp_path):
        """If a JSON entry is removed, sync should delete it from DB."""
        db_file = tmp_path / "prune_test.db"
        # First sync with full catalog
        subprocess.run(
            [sys.executable, str(BASE_DIR / "sync_catalog.py"),
             "--db", str(db_file), "--catalog", str(CATALOG_PATH)],
            capture_output=True, text=True, cwd=str(BASE_DIR),
        )

        # Create a minimal catalog
        mini_catalog = {
            "_metadata": {"schema_version": "1.0", "last_updated": "2026-01-01"},
            "service_aliases": [
                {"alias": "vm", "service_name": "Virtual Machines", "category": "Compute"}
            ],
            "deprecated_services": []
        }
        mini_path = tmp_path / "mini_catalog.json"
        with open(mini_path, "w") as f:
            json.dump(mini_catalog, f)

        # Re-sync with mini catalog
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "sync_catalog.py"),
             "--db", str(db_file), "--catalog", str(mini_path)],
            capture_output=True, text=True, cwd=str(BASE_DIR),
        )
        assert result.returncode == 0

        conn = sqlite3.connect(str(db_file))
        count = conn.execute("SELECT COUNT(*) FROM service_aliases").fetchone()[0]
        conn.close()
        assert count == 1, f"Prune failed: expected 1 alias, got {count}"

    def test_sync_updates_changed_entries(self, tmp_path):
        """If a service_name changes in JSON, sync should update DB."""
        db_file = tmp_path / "update_test.db"
        # Initial catalog
        catalog_v1 = {
            "_metadata": {"schema_version": "1.0", "last_updated": "2026-01-01"},
            "service_aliases": [
                {"alias": "test-svc", "service_name": "OldName", "category": "Test"}
            ],
            "deprecated_services": []
        }
        catalog_path = tmp_path / "catalog.json"
        with open(catalog_path, "w") as f:
            json.dump(catalog_v1, f)

        subprocess.run(
            [sys.executable, str(BASE_DIR / "sync_catalog.py"),
             "--db", str(db_file), "--catalog", str(catalog_path)],
            capture_output=True, text=True, cwd=str(BASE_DIR),
        )

        # Update
        catalog_v1["service_aliases"][0]["service_name"] = "NewName"
        with open(catalog_path, "w") as f:
            json.dump(catalog_v1, f)

        subprocess.run(
            [sys.executable, str(BASE_DIR / "sync_catalog.py"),
             "--db", str(db_file), "--catalog", str(catalog_path)],
            capture_output=True, text=True, cwd=str(BASE_DIR),
        )

        conn = sqlite3.connect(str(db_file))
        row = conn.execute(
            "SELECT service_name FROM service_aliases WHERE alias = 'test-svc'"
        ).fetchone()
        conn.close()
        assert row[0] == "NewName", f"Update failed: got '{row[0]}'"

    def test_dry_run_makes_no_changes(self, tmp_path):
        """--dry-run should not modify DB."""
        db_file = tmp_path / "dryrun_test.db"
        # Initial sync
        subprocess.run(
            [sys.executable, str(BASE_DIR / "sync_catalog.py"),
             "--db", str(db_file), "--catalog", str(CATALOG_PATH)],
            capture_output=True, text=True, cwd=str(BASE_DIR),
        )
        size_before = db_file.stat().st_size

        # Dry run with mini catalog (would prune everything)
        mini = {
            "_metadata": {"schema_version": "1.0", "last_updated": "2026-01-01"},
            "service_aliases": [{"alias": "x", "service_name": "X", "category": "T"}],
            "deprecated_services": []
        }
        mini_path = tmp_path / "mini.json"
        with open(mini_path, "w") as f:
            json.dump(mini, f)

        subprocess.run(
            [sys.executable, str(BASE_DIR / "sync_catalog.py"),
             "--db", str(db_file), "--catalog", str(mini_path), "--dry-run"],
            capture_output=True, text=True, cwd=str(BASE_DIR),
        )

        conn = sqlite3.connect(str(db_file))
        count = conn.execute("SELECT COUNT(*) FROM service_aliases").fetchone()[0]
        conn.close()
        # Should still have all original aliases, not 1
        with open(CATALOG_PATH) as f:
            full = json.load(f)
        assert count == len(full["service_aliases"]), \
            f"--dry-run modified DB: got {count} aliases"


# ===========================================================================
# 3. SQLite Schema
# ===========================================================================

class TestSQLiteSchema:
    """Validate the SQLite database schema."""

    def test_service_aliases_columns(self, tmp_db_conn):
        cursor = tmp_db_conn.execute("PRAGMA table_info(service_aliases)")
        cols = {row["name"] for row in cursor.fetchall()}
        expected = {"alias", "service_name", "service_family", "category",
                    "source", "source_date", "updated_at"}
        assert expected == cols, f"Column mismatch: expected {expected}, got {cols}"

    def test_deprecated_services_columns(self, tmp_db_conn):
        cursor = tmp_db_conn.execute("PRAGMA table_info(deprecated_services)")
        cols = {row["name"] for row in cursor.fetchall()}
        expected = {"alias", "service_name", "status", "retirement_date",
                    "replacement", "message", "source", "source_date", "updated_at"}
        assert expected == cols, f"Column mismatch: expected {expected}, got {cols}"

    def test_azure_services_columns(self, tmp_db_conn):
        cursor = tmp_db_conn.execute("PRAGMA table_info(azure_services)")
        cols = {row["name"] for row in cursor.fetchall()}
        expected = {"service_name", "service_family", "discovered_at",
                    "last_seen_at", "is_active"}
        assert expected == cols

    def test_sync_log_columns(self, tmp_db_conn):
        cursor = tmp_db_conn.execute("PRAGMA table_info(sync_log)")
        cols = {row["name"] for row in cursor.fetchall()}
        expected = {"id", "action", "table_name", "key_value", "details", "synced_at"}
        assert expected == cols

    def test_alias_primary_key(self, tmp_db_conn):
        cursor = tmp_db_conn.execute("PRAGMA table_info(service_aliases)")
        pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"]]
        assert pk_cols == ["alias"]

    def test_sku_tiers_table_exists(self, tmp_db_conn):
        tables = {row[0] for row in tmp_db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "sku_tiers" in tables

    def test_sku_tiers_columns(self, tmp_db_conn):
        cursor = tmp_db_conn.execute("PRAGMA table_info(sku_tiers)")
        cols = {row["name"] for row in cursor.fetchall()}
        expected = {"service_name", "tier_name", "unit_count", "unit_name",
                    "description", "api_sku_name", "api_unit",
                    "source", "source_date", "updated_at"}
        assert expected == cols


# ===========================================================================
# 3b. SKU Tiers
# ===========================================================================

class TestSkuTiers:
    """Validate SKU tier sync and server tier pricing."""

    def test_catalog_has_sku_tiers(self, catalog):
        assert "sku_tiers" in catalog
        assert len(catalog["sku_tiers"]) > 0

    def test_sku_tier_entries_have_required_fields(self, catalog):
        for svc in catalog["sku_tiers"]:
            assert "service_name" in svc
            assert "tiers" in svc
            assert isinstance(svc["tiers"], list)
            for tier in svc["tiers"]:
                assert "name" in tier
                assert "units" in tier

    def test_fabric_tiers_synced(self, tmp_db_conn):
        rows = tmp_db_conn.execute(
            "SELECT tier_name, unit_count FROM sku_tiers WHERE service_name = 'Microsoft Fabric' ORDER BY unit_count"
        ).fetchall()
        assert len(rows) == 11
        assert rows[0]["tier_name"] == "F2"
        assert rows[0]["unit_count"] == 2
        assert rows[-1]["tier_name"] == "F2048"
        assert rows[-1]["unit_count"] == 2048

    def test_cosmos_tiers_synced(self, tmp_db_conn):
        rows = tmp_db_conn.execute(
            "SELECT COUNT(*) FROM sku_tiers WHERE service_name = 'Azure Cosmos DB'"
        ).fetchone()
        assert rows[0] == 5

    def test_tier_provenance_stored(self, tmp_db_conn):
        row = tmp_db_conn.execute(
            "SELECT source, source_date FROM sku_tiers WHERE service_name = 'Microsoft Fabric' LIMIT 1"
        ).fetchone()
        assert row["source"] is not None and len(row["source"]) > 0
        assert row["source_date"] is not None

    def test_server_list_tier_pricing(self):
        if not DB_PATH.exists():
            pytest.skip("Production DB not present")
        from azure_pricing_server import AzurePricingServer
        server = AzurePricingServer()
        tiers = server.list_tier_pricing("Microsoft Fabric", 0.18)
        assert tiers is not None
        assert len(tiers) == 11
        f64 = [t for t in tiers if t["tier_name"] == "F64"][0]
        assert f64["unit_count"] == 64
        assert f64["hourly_cost"] == 11.52
        assert f64["monthly_cost"] == 8409.6

    def test_server_get_single_tier(self):
        if not DB_PATH.exists():
            pytest.skip("Production DB not present")
        from azure_pricing_server import AzurePricingServer
        server = AzurePricingServer()
        r = server.get_tier_pricing("Microsoft Fabric", "F256", 0.18)
        assert r is not None
        assert r["unit_count"] == 256
        assert r["hourly_cost"] == 46.08
        assert "source" in r
        assert "source_date" in r

    def test_server_tier_returns_none_for_unknown(self):
        if not DB_PATH.exists():
            pytest.skip("Production DB not present")
        from azure_pricing_server import AzurePricingServer
        server = AzurePricingServer()
        assert server.get_tier_pricing("NonexistentService", "X1", 1.0) is None
        assert server.list_tier_pricing("NonexistentService", 1.0) is None


# ===========================================================================
# 3c. Provenance
# ===========================================================================

class TestProvenance:
    """Validate source provenance data is stored."""

    def test_aliases_have_source_columns(self, tmp_db_conn):
        row = tmp_db_conn.execute(
            "SELECT source, source_date FROM service_aliases LIMIT 1"
        ).fetchone()
        assert row is not None
        # Should have inherited default_source from metadata
        assert row["source"] is not None

    def test_default_source_propagated(self, tmp_db_conn, catalog):
        default_source = catalog["_metadata"].get("default_source", "")
        row = tmp_db_conn.execute(
            "SELECT source FROM service_aliases WHERE alias = 'vm'"
        ).fetchone()
        assert row["source"] == default_source


# ===========================================================================
# 4. AzurePricingServer Loading
# ===========================================================================

class TestServerLoading:
    """Test that AzurePricingServer loads data from SQLite correctly."""

    def test_server_imports(self):
        from azure_pricing_server import AzurePricingServer
        assert AzurePricingServer is not None

    def test_server_loads_aliases_from_production_db(self):
        """Server loads from azure_services.db when it exists."""
        if not DB_PATH.exists():
            pytest.skip("Production DB not present; run sync_catalog.py first")
        from azure_pricing_server import AzurePricingServer
        server = AzurePricingServer()
        assert len(server.service_mappings) > 100

    def test_server_loads_deprecated_from_production_db(self):
        if not DB_PATH.exists():
            pytest.skip("Production DB not present")
        from azure_pricing_server import AzurePricingServer
        server = AzurePricingServer()
        assert len(server.deprecated_service_mappings) > 0

    def test_server_graceful_fallback_no_db(self, tmp_path, monkeypatch):
        """Server should not crash if DB is missing — just use empty dicts."""
        from azure_pricing_server import AzurePricingServer
        server = AzurePricingServer()
        monkeypatch.setattr(type(server), "DB_PATH", tmp_path / "nonexistent.db")
        server._service_mappings = None  # reset cache
        server._deprecated_service_mappings = None
        assert server.service_mappings == {}
        assert server.deprecated_service_mappings == {}

    def test_server_lazy_loading(self):
        """Mappings should not be loaded until first access."""
        from azure_pricing_server import AzurePricingServer
        server = AzurePricingServer()
        assert server._service_mappings is None
        assert server._deprecated_service_mappings is None
        # Access triggers load
        _ = server.service_mappings
        assert server._service_mappings is not None


# ===========================================================================
# 5. Alias Lookup Correctness
# ===========================================================================

class TestAliasLookups:
    """Verify key alias mappings resolve correctly."""

    @pytest.fixture(autouse=True)
    def _load_server(self):
        if not DB_PATH.exists():
            pytest.skip("Production DB not present")
        from azure_pricing_server import AzurePricingServer
        self.server = AzurePricingServer()

    # --- Core services ---
    @pytest.mark.parametrize("alias,expected", [
        ("vm", "Virtual Machines"),
        ("vms", "Virtual Machines"),
        ("virtual machine", "Virtual Machines"),
        ("compute", "Virtual Machines"),
        ("aks", "Azure Kubernetes Service"),
        ("k8s", "Azure Kubernetes Service"),
        ("kubernetes", "Azure Kubernetes Service"),
        ("app service", "Azure App Service"),
        ("web app", "Azure App Service"),
        ("sql", "SQL Database"),
        ("sql database", "SQL Database"),
        ("cosmos", "Azure Cosmos DB"),
        ("cosmosdb", "Azure Cosmos DB"),
        ("storage", "Storage"),
        ("blob", "Storage"),
        ("redis", "Redis Cache"),
        ("cache", "Redis Cache"),
    ])
    def test_core_service_aliases(self, alias, expected):
        assert self.server.service_mappings.get(alias) == expected

    # --- AI/ML ---
    @pytest.mark.parametrize("alias,expected", [
        ("openai", "Foundry Models"),
        ("gpt", "Foundry Models"),
        ("gpt-4", "Foundry Models"),
        ("ai", "Foundry Tools"),
        ("cognitive services", "Foundry Tools"),
        ("machine learning", "Azure Machine Learning"),
        ("aml", "Azure Machine Learning"),
        ("ai search", "Azure Cognitive Search"),
    ])
    def test_ai_aliases(self, alias, expected):
        assert self.server.service_mappings.get(alias) == expected

    # --- Networking ---
    @pytest.mark.parametrize("alias,expected", [
        ("vnet", "Virtual Network"),
        ("load balancer", "Load Balancer"),
        ("vpn", "VPN Gateway"),
        ("expressroute", "ExpressRoute"),
        ("ddos", "Azure DDOS Protection"),
        ("front door", "Azure Front Door Service"),
        ("cdn", "Content Delivery Network"),
        ("firewall", "Azure Firewall"),
        ("bastion", "Azure Bastion"),
    ])
    def test_networking_aliases(self, alias, expected):
        assert self.server.service_mappings.get(alias) == expected

    # --- New gap services ---
    @pytest.mark.parametrize("alias,expected", [
        ("databricks", "Azure Databricks"),
        ("data factory", "Azure Data Factory v2"),
        ("fabric", "Microsoft Fabric"),
        ("sentinel", "Sentinel"),
        ("iot hub", "IoT Hub"),
        ("avd", "Windows Virtual Desktop"),
        ("backup", "Backup"),
        ("netapp", "Azure NetApp Files"),
        ("container instances", "Container Instances"),
        ("sql managed instance", "SQL Managed Instance"),
        ("automation", "Automation"),
        ("site recovery", "Azure Site Recovery"),
        ("azure policy", "Azure Policy"),
        ("quantum", "Quantum Computing"),
        ("power apps", "Power Apps"),
    ])
    def test_gap_service_aliases(self, alias, expected):
        assert self.server.service_mappings.get(alias) == expected


# ===========================================================================
# 6. Deprecated Service Lookups
# ===========================================================================

class TestDeprecatedLookups:
    """Verify deprecated service entries load correctly."""

    @pytest.fixture(autouse=True)
    def _load_server(self):
        if not DB_PATH.exists():
            pytest.skip("Production DB not present")
        from azure_pricing_server import AzurePricingServer
        self.server = AzurePricingServer()

    def test_luis_is_retired(self):
        dep = self.server.deprecated_service_mappings.get("luis")
        assert dep is not None
        assert dep["status"] == "retired"
        assert dep["service"] == "Foundry Tools"

    def test_qna_maker_is_retired(self):
        dep = self.server.deprecated_service_mappings.get("qna maker")
        assert dep is not None
        assert dep["status"] == "retired"

    def test_form_recognizer_is_rebranded(self):
        dep = self.server.deprecated_service_mappings.get("form recognizer")
        assert dep is not None
        assert dep["status"] == "rebranded"
        assert "Document Intelligence" in dep["replacement"]

    def test_all_deprecated_have_message(self):
        for alias, info in self.server.deprecated_service_mappings.items():
            assert info.get("message"), f"Deprecated '{alias}' missing message"

    def test_all_deprecated_have_replacement(self):
        for alias, info in self.server.deprecated_service_mappings.items():
            assert info.get("replacement"), f"Deprecated '{alias}' missing replacement"


# ===========================================================================
# 7. Full Coverage Validation
# ===========================================================================

class TestFullCoverage:
    """Validate that all API-discovered services have at least one alias."""

    def test_all_api_services_covered(self):
        """Every service in azure_services should be a target of at least one alias."""
        if not DB_PATH.exists():
            pytest.skip("Production DB not present")
        conn = sqlite3.connect(str(DB_PATH))
        api_services = {
            row[0] for row in conn.execute(
                "SELECT service_name FROM azure_services WHERE is_active = 1"
            ).fetchall()
        }
        aliased_targets = {
            row[0] for row in conn.execute(
                "SELECT DISTINCT service_name FROM service_aliases"
            ).fetchall()
        }
        conn.close()

        if not api_services:
            pytest.skip("No API services discovered; run sync_catalog.py --from-api")

        uncovered = api_services - aliased_targets
        coverage_pct = (len(api_services) - len(uncovered)) * 100 // len(api_services)
        assert len(uncovered) == 0, \
            f"{len(uncovered)} services uncovered ({coverage_pct}% coverage): {sorted(uncovered)}"

    def test_alias_count_minimum(self):
        """Sanity check: we should have at least 300 aliases."""
        if not DB_PATH.exists():
            pytest.skip("Production DB not present")
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM service_aliases").fetchone()[0]
        conn.close()
        assert count >= 300, f"Only {count} aliases — expected 300+"
