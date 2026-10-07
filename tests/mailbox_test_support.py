"""Seed SQL esplicito delle caselle temporanee dei test di integrazione."""
from pathlib import Path

from pct.email_mailbox_repository import EmailMailboxRepository
from pct.email_sql_client import GestioneEmailSQL
from pct.storage import StudioDB


def sql_mailbox(db_path, *, tenant_key="single-tenant"):
    path = Path(db_path).resolve()
    assert path.parent.name == "email"
    kind = {"casella.json": "pec", "ordinaria.json": "ordinary"}[path.name]
    root = path.parent.parent
    root.mkdir(parents=True, exist_ok=True)
    db = StudioDB.get(str(root / "studio.db"))
    repository = EmailMailboxRepository(db, tenant_key, kind, mirror_path=path)
    repository.ensure_schema()
    marker = db.conn.execute(
        "SELECT 1 FROM email_mailbox_bootstrap WHERE tenant_key=? AND mailbox_kind=?",
        (tenant_key, kind),
    ).fetchone()
    if marker is None:
        # Il test crea una casella nuova; mai importare un mirror implicitamente.
        repository.initialize({}, source_of_truth="sqlite")
    return GestioneEmailSQL(str(path), studio_db=db, tenant_key=tenant_key,
                           mailbox_kind=kind, tenant_root=root, actor_key="test")
