from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQLITE_SCHEMA = (ROOT / "pct" / "sql" / "20260824_fascicolo_document_catalog.sql").read_text(encoding="utf-8")
POSTGRES_SCHEMA = (ROOT / "pct" / "sql" / "20260824_fascicolo_document_catalog_postgres.sql").read_text(encoding="utf-8")


TABLES = {
    "document_catalog_rule_sets",
    "document_catalog_source_snapshots",
    "document_catalog_jobs",
    "document_catalog_assignments",
    "document_catalog_candidates",
    "document_catalog_evidence",
    "document_catalog_reviews",
}

ASSIGNMENT_COLUMNS = {
    "tenant_id", "fascicolo_id", "document_id", "document_ai_id", "document_version_id",
    "document_sha256", "profile_id", "legal_area", "legal_branch", "legal_subfamily",
    "document_nature", "document_label", "document_section", "deposit_role", "status",
    "confidence", "source_state", "resolver_version", "reason", "created_at", "updated_at",
}


def _table_block(schema: str, table: str) -> str:
    start = schema.index(f"CREATE TABLE IF NOT EXISTS {table} (")
    return schema[start:schema.index(");", start)]


def test_catalog_schema_sqlite_e_postgresql_hanno_stesso_contratto_operativo():
    for table in TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table} (" in SQLITE_SCHEMA
        assert f"CREATE TABLE IF NOT EXISTS {table} (" in POSTGRES_SCHEMA

    sqlite_assignment = _table_block(SQLITE_SCHEMA, "document_catalog_assignments")
    postgres_assignment = _table_block(POSTGRES_SCHEMA, "document_catalog_assignments")
    for column in ASSIGNMENT_COLUMNS:
        assert f"{column} " in sqlite_assignment
        assert f"{column} " in postgres_assignment

    for schema in (SQLITE_SCHEMA, POSTGRES_SCHEMA):
        assert "UNIQUE (tenant_id, fascicolo_id, document_id, document_sha256, resolver_version)" in schema
        assert "FOREIGN KEY (assignment_id)" in schema or "assignment_id TEXT NOT NULL REFERENCES" in schema
        assert "status IN ('proposed', 'confirmed', 'review_required', 'superseded', 'rejected')" in schema
        assert "status IN ('queued', 'processing', 'completed', 'review_required', 'error')" in schema
        assert "source_state IN ('verified_snapshot', 'manual_browser_evidence', 'manual_override', 'review_required')" in schema
