"""legal-grade audit WORM indexes

Revision ID: 20260513_legal_audit_worm
Revises:
Create Date: 2026-05-13
"""

from __future__ import annotations

from pathlib import Path

from alembic import op


revision = "20260513_legal_audit_worm"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_path = Path(__file__).resolve().parents[2] / "pct" / "sql" / "20260513_legal_audit_worm_postgres.sql"
    op.execute(sql_path.read_text(encoding="utf-8"))


def downgrade() -> None:
    # Legal audit tables are append-only evidence indexes. Downgrade is
    # intentionally disabled to avoid accidental evidence metadata removal.
    raise RuntimeError("Downgrade audit probatorio non consentito.")
