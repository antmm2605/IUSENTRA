from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from pct.notifications import NotificationRepository
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from web.services import notifications_runtime


def _write_fascicolo(db_path: Path, documents: list[dict[str, object]]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fascicoli (
                id TEXT PRIMARY KEY,
                titolo TEXT,
                oggetto TEXT,
                stato TEXT,
                documenti_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO fascicoli (id, titolo, oggetto, stato, documenti_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                titolo=excluded.titolo,
                oggetto=excluded.oggetto,
                stato=excluded.stato,
                documenti_json=excluded.documenti_json
            """,
            (
                "FNEW",
                "Provvedimento nuovo c. MIM",
                "Provvedimento nuovo c. MIM",
                "APERTO",
                json.dumps(documents),
            ),
        )


def _paths(tmp_path: Path) -> dict[str, str]:
    return {
        "STUDIO_DB": str(tmp_path / "tenant" / "studio.db"),
        "NOTIFICATIONS_DB": str(tmp_path / "tenant" / "notifications" / "notifications.db"),
        "SCADENZIARIO_DB": str(tmp_path / "tenant" / "scadenziario" / "scadenze.json"),
    }


def test_materializzatore_notifiche_residue_alimenta_topbar_push_e_scadenziario(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [
            {
                "id": "doc-1",
                "nome": "Provvedimento da notificare - decreto del 20/07/2026.pdf",
                "tipo": "PROVVEDIMENTO",
                "classificazione_portale": "comunicazione_cancelleria",
                "note": "Provvedimento da notificare in data 20/07/2026.",
                "data_documento": "2026-07-20",
            }
        ],
    )
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [
            SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)
        ],
    )

    report = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert report["ok"] is True
    assert report["scanned"] == 1
    assert report["items"] == 1
    assert report["to_notify"] == 1
    assert report["recipients"] == 1
    records = NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications("tenant-test", "admin")
    assert len(records) == 1
    assert records[0].source_type == "legal_notification_presidio"
    assert records[0].href.endswith("#relata-notifica") or "/notifiche-legali" in records[0].href

    deadlines = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    assert len(deadlines) == 1
    assert deadlines[0].tipo == TipoTermine.NOTIFICA
    assert deadlines[0].stato == StatoTermine.APERTO
    assert "IUSENTRA_LEGAL_NOTIFICATION:legal-notification:FNEW:da_preparare" in deadlines[0].note

    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [
            {
                "id": "doc-2",
                "nome": "Ricorso Verdi (originale notificato).pdf",
                "tipo": "RICORSO",
                "classificazione_portale": "Gestionale precedente",
                "note": "data notifica: 18/07/2026 ore: 10:20 Notifica ID: LEGACY",
                "tags": ["quickorganizer", "import-pratiche"],
            },
            {
                "id": "doc-3",
                "nome": "Relata di notifica.pdf",
                "tipo": "NOTIFICA",
                "classificazione_portale": "Gestionale precedente",
                "note": "data notifica: 18/07/2026 ore: 10:20 Notifica ID: LEGACY",
                "tags": ["quickorganizer", "import-pratiche"],
            },
        ],
    )

    second = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert second["items"] == 0
    assert second["to_notify"] == 0
    assert NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications("tenant-test", "admin") == []
    closed = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    assert closed[0].stato == StatoTermine.COMPLETATO
