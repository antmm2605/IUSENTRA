from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.notifications import NotificationRecord, NotificationRepository
from pct.pec_notification_presidio import NotificationPresidioRepository, NotificationPresidioService, ReceiptKind
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from pct.storage import StudioDB
from web.services import notifications_runtime, react_agenda_bridge, react_scadenziario_bridge
import pct.core_storage_backend as core_storage_backend
import pct.pec_notification_presidio as notification_presidio_module


def _write_fascicolo(
    db_path: Path,
    documents: list[dict[str, object]],
    *,
    fascicolo_id: str = "FNEW",
    titolo: str = "Provvedimento nuovo c. MIM",
    nome_cliente: str = "",
    numero_rg: str = "",
    anno_rg: str = "",
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = StudioDB.get(str(db_path))
    db.ensure_schema()
    db.chiudi()
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fascicoli (
                id TEXT PRIMARY KEY,
                titolo TEXT,
                oggetto TEXT,
                nome_cliente TEXT,
                numero_rg TEXT,
                anno_rg TEXT,
                stato TEXT,
                documenti_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO fascicoli
            (id, titolo, oggetto, nome_cliente, numero_rg, anno_rg, stato, documenti_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                titolo=excluded.titolo,
                oggetto=excluded.oggetto,
                nome_cliente=excluded.nome_cliente,
                numero_rg=excluded.numero_rg,
                anno_rg=excluded.anno_rg,
                stato=excluded.stato,
                documenti_json=excluded.documenti_json
            """,
            (
                fascicolo_id,
                titolo,
                titolo,
                nome_cliente,
                numero_rg,
                anno_rg,
                "APERTO",
                json.dumps(documents),
            ),
        )


def _paths(tmp_path: Path) -> dict[str, str]:
    return {
        "STUDIO_DB": str(tmp_path / "tenant" / "studio.db"),
        "PEC_AUDIT_DB": str(tmp_path / "tenant" / "email" / "pec_audit.sqlite"),
        "NOTIFICATIONS_DB": str(tmp_path / "tenant" / "notifications" / "notifications.db"),
        "SCADENZIARIO_DB": str(tmp_path / "tenant" / "scadenziario" / "scadenze.json"),
        "_TENANT_PRESIDIO_ID": "tenant-test",
    }


def _fake_postgres_database() -> SimpleNamespace:
    return SimpleNamespace(
        normalized_mode="POSTGRESQL",
        connessione_ok=True,
        core_runtime_enabled=True,
        host="127.0.0.1",
        db_name="iusentra_test",
        utente="iusentra",
        password="",
        porta_effettiva=5432,
        ssl=False,
    )


class _FakeCoreBackend:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def fetchall_readonly(self, sql: str, parameters: tuple[object, ...] = ()) -> list[dict[str, object]]:
        self.calls.append((sql, parameters))
        return list(self.rows)


class _FakeQueryResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, object]]:
        return list(self._rows)


class _FakePresidioConnection:
    def __init__(self, repo: "_FakeNotificationPresidioRepository") -> None:
        self.repo = repo

    def __enter__(self) -> "_FakePresidioConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, sql: str, params: tuple[object, ...]):
        self.repo.executed_sql = sql
        self.repo.executed_params = params
        return _FakeQueryResult(
            [
                {
                    "id": "pg-presidio",
                    "fascicolo_id": "PGF",
                    "source_message_id": "pec-pg",
                    "status": "DETECTED",
                    "priority": "P1",
                    "notification_case": "judgment_to_notify_review",
                    "detection_reason": "Sentenza da verificare.",
                    "source_effective_at": "2026-07-20T10:00:00Z",
                    "updated_at": "2026-07-20T10:05:00Z",
                    "source_document_id": "DOC-PG",
                    "source_document_name": "sentenza-pg.pdf",
                }
            ]
        )


class _FakeNotificationPresidioRepository:
    instances: list["_FakeNotificationPresidioRepository"] = []

    def __init__(self, db_path: object, *, tenant_id: str, postgres_dsn: str = "", **_kwargs: object) -> None:
        self.db_path = db_path
        self.tenant_id = tenant_id
        self.postgres_dsn = postgres_dsn
        self.executed_sql = ""
        self.executed_params: tuple[object, ...] = ()
        self.closed = False
        self.__class__.instances.append(self)

    def connection(self) -> _FakePresidioConnection:
        return _FakePresidioConnection(self)

    def close(self) -> None:
        self.closed = True

    @staticmethod
    def _row(row: object) -> dict[str, object]:
        return dict(row) if isinstance(row, dict) else {}


def _seed_advanced_presidio(paths: dict[str, str], tenant_id: str = "tenant-test") -> str:
    repo = NotificationPresidioRepository(paths["PEC_AUDIT_DB"], tenant_id=tenant_id)
    try:
        service = NotificationPresidioService(repo)
        result = service.create_candidate(
            {
                "fascicolo_id": "C3565650",
                "source_message_id": "pec_alfano",
                "source_parsed_version_id": "parsed-1",
                "legal_event_id": "event-alfano",
                "source_effective_at": "2026-07-20T11:01:03Z",
                "pec_official_delivery_at": "2026-07-20T11:01:03Z",
                "event_or_order_at": "2026-07-20T11:01:03Z",
                "live_pec_operational_event": True,
                "trigger_type": "STRATEGIC_NOTIFICATION_REVIEW",
                "notification_case": "judgment_to_notify_review",
                "channel": "pec",
                "priority": "P1",
                "confidence": 0.86,
                "human_review_required": True,
                "detection_reason": "Sentenza ex art. 429 c.p.c. da valutare per notifica.",
                "rulepack_version": "pytest",
                "documents": [
                    {
                        "source_message_id": "pec_alfano",
                        "document_role": "office_pec_copy",
                        "document_version": "1",
                        "original_filename": "19040620s.pdf",
                        "authoritative": True,
                    }
                ],
                "recipients": [
                    {"name": "Ministero dell'Istruzione e del Merito", "role": "controparte", "required": True}
                ],
            }
        )
        return str(result["id"])
    finally:
        repo.close()


def _seed_paginated_advanced_presidia(
    paths: dict[str, str],
    indices: range,
    *,
    tenant_id: str = "tenant-test",
) -> None:
    repo = NotificationPresidioRepository(paths["PEC_AUDIT_DB"], tenant_id=tenant_id)
    try:
        base = datetime(2026, 7, 20, 8, 0, 0)
        rows = []
        for index in indices:
            presidio_id = f"page-presidio-{index:03d}"
            timestamp = (base + timedelta(minutes=index)).isoformat(timespec="seconds") + "Z"
            rows.append(
                (
                    presidio_id,
                    tenant_id,
                    f"PAGE-FASC-{index:03d}",
                    f"pec-page-{index:03d}",
                    "STRATEGIC_NOTIFICATION_REVIEW",
                    "judgment_to_notify_review",
                    "DETECTED",
                    "P1",
                    "pytest-pagination",
                    f"pytest-pagination:{index:03d}",
                    f"pytest-pagination-instance:{index:03d}",
                    timestamp,
                    timestamp,
                )
            )
        with repo.connection() as conn:
            conn.executemany(
                """
                INSERT INTO pec_legal_notification_presidia
                (id, tenant_id, fascicolo_id, source_message_id, trigger_type,
                 notification_case, status, priority, rulepack_version, dedupe_key,
                 notification_instance_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
    finally:
        repo.close()


def _advance_presidio_to_proof_to_deposit(
    paths: dict[str, str], presidio_id: str, tenant_id: str = "tenant-test"
) -> None:
    repo = NotificationPresidioRepository(paths["PEC_AUDIT_DB"], tenant_id=tenant_id)
    try:
        with repo.connection() as conn:
            recipient = conn.execute(
                """
                SELECT id FROM pec_legal_notification_recipients
                WHERE tenant_id=? AND presidio_id=?
                ORDER BY id
                LIMIT 1
                """,
                (tenant_id, presidio_id),
            ).fetchone()
        assert recipient is not None
        repo.mark_recipient_event(
            str(recipient["id"]),
            kind=ReceiptKind.RDAC,
            message_id="rdac-alfano",
            occurred_at="2026-07-20T12:10:00Z",
        )
        repo.transition(
            presidio_id,
            "DELIVERY_COMPLETE",
            actor="pytest",
            reason="RdAC completa per il test del materializzatore.",
            evidence={"source": "pytest"},
            idempotency_key=f"pytest-delivery-complete:{presidio_id}",
        )
        repo.transition(
            presidio_id,
            "PROOF_TO_DEPOSIT",
            actor="pytest",
            reason="Prova da depositare per il test del materializzatore.",
            evidence={"source": "pytest"},
            idempotency_key=f"pytest-proof-to-deposit:{presidio_id}",
        )
    finally:
        repo.close()


def _advance_presidio_to_proof_deposited(
    paths: dict[str, str], presidio_id: str, tenant_id: str = "tenant-test"
) -> None:
    repo = NotificationPresidioRepository(paths["PEC_AUDIT_DB"], tenant_id=tenant_id)
    try:
        repo.transition(
            presidio_id,
            "PROOF_DEPOSITED",
            actor="pytest",
            reason="Prova di notifica depositata per il test del materializzatore.",
            evidence={"source": "pytest"},
            idempotency_key=f"pytest-proof-deposited:{presidio_id}",
        )
    finally:
        repo.close()


def test_notification_fascicolo_rows_usa_backend_core_sqlite(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(Path(paths["STUDIO_DB"]), [], fascicolo_id="FOPEN", titolo="Fascicolo aperto")
    _write_fascicolo(Path(paths["STUDIO_DB"]), [], fascicolo_id="FARCH", titolo="Fascicolo archiviato")
    with sqlite3.connect(paths["STUDIO_DB"]) as conn:
        conn.execute("UPDATE fascicoli SET stato='archiviato' WHERE id='FARCH'")

    total, archived, rows = notifications_runtime._notification_fascicolo_rows(paths)

    assert total == 2
    assert archived == 1
    assert [_id for _id in [notifications_runtime._notification_row_value(row, "id") for row in rows]] == ["FOPEN"]


def test_notification_fascicolo_rows_usa_backend_core_postgres_compat(monkeypatch) -> None:
    database = _fake_postgres_database()
    backend = _FakeCoreBackend(
        [
            {
                "id": "PGF",
                "titolo": "Sentenza PG",
                "nome_cliente": "Cliente PG",
                "numero_rg": "1",
                "anno_rg": "2026",
                "stato": "APERTO",
                "documenti_json": "[]",
            },
            {
                "id": "PGARCH",
                "titolo": "Archiviato PG",
                "stato": "archiviato",
                "documenti_json": "[]",
            },
        ]
    )

    def _build_backend(config, *, studio_db_path: str):
        assert config is database
        assert studio_db_path == "postgres-core-placeholder.db"
        return backend

    monkeypatch.setattr(core_storage_backend, "build_core_storage_backend", _build_backend)

    total, archived, rows = notifications_runtime._notification_fascicolo_rows(
        {"STUDIO_DB": "postgres-core-placeholder.db"},
        database,
    )

    assert total == 2
    assert archived == 1
    assert [notifications_runtime._notification_row_value(row, "id") for row in rows] == ["PGF"]
    assert backend.calls == [
        (
            "SELECT id, numero AS codice, titolo, oggetto, nome_cliente, controparte, "
            "tribunale AS ufficio, numero_rg, anno_rg, stato, documenti_json FROM fascicoli",
            (),
        )
    ]


def test_notification_fascicolo_rows_postgres_fail_closed_non_legge_sqlite(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(Path(paths["STUDIO_DB"]), [], fascicolo_id="LOCAL", titolo="Non deve uscire")
    database = _fake_postgres_database()
    monkeypatch.setattr(core_storage_backend, "build_core_storage_backend", lambda *_args, **_kwargs: None)

    total, archived, rows = notifications_runtime._notification_fascicolo_rows(paths, database)

    assert (total, archived, rows) == (0, 0, [])


def test_advanced_notification_items_usa_pec_audit_sqlite_anche_con_core_postgres(
    monkeypatch,
    tmp_path: Path,
) -> None:
    database = _fake_postgres_database()
    audit_db = tmp_path / "tenant" / "email" / "pec_audit.sqlite"
    audit_db.parent.mkdir(parents=True, exist_ok=True)
    audit_db.touch()
    backend = _FakeCoreBackend(
        [
            {
                "id": "PGF",
                "titolo": "Sentenza PG",
                "nome_cliente": "Cliente PG",
                "numero_rg": "1",
                "anno_rg": "2026",
                "stato": "APERTO",
                "documenti_json": "[]",
            }
        ]
    )
    _FakeNotificationPresidioRepository.instances = []
    monkeypatch.setattr(core_storage_backend, "build_core_storage_backend", lambda *_args, **_kwargs: backend)
    monkeypatch.setattr(
        notification_presidio_module, "NotificationPresidioRepository", _FakeNotificationPresidioRepository
    )

    items = notifications_runtime._advanced_notification_items(
        {
            "STUDIO_DB": "postgres-core-placeholder.db",
            "PEC_AUDIT_DB": str(audit_db),
        },
        tenant_id="studio-montagnese",
        database=database,
    )

    assert len(items) == 1
    repo = _FakeNotificationPresidioRepository.instances[0]
    assert Path(repo.db_path) == audit_db
    assert repo.tenant_id == "studio-montagnese"
    assert repo.postgres_dsn == ""
    assert repo.closed is True
    assert "sqlite_master" not in repo.executed_sql.lower()
    assert "p.tenant_id=?" in repo.executed_sql
    assert repo.executed_params[0] == "studio-montagnese"
    assert backend.calls == [
        (
            "SELECT id, numero AS codice, titolo, oggetto, nome_cliente, controparte, "
            "tribunale AS ufficio, numero_rg, anno_rg, stato, documenti_json "
            "FROM fascicoli WHERE id IN (?)",
            ("PGF",),
        )
    ]
    assert "Cliente PG" in items[0]["title"]
    assert items[0]["sourceDocumentId"] == "DOC-PG"
    assert items[0]["sourceDocumentName"] == "sentenza-pg.pdf"
    assert "d.document_role='portal_original'" in repo.executed_sql


def test_materializzatore_separa_slug_presidi_da_id_tecnico_notifiche(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths["_TENANT_PRESIDIO_ID"] = "studio-montagnese"
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    presidio_id = _seed_advanced_presidio(paths, tenant_id="studio-montagnese")
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    report = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-montagnese",
        tenant_id="tenant-local-studio-montagnese",
        presidio_tenant_id="studio-montagnese",
    )

    assert report["ok"] is True
    assert report["advanced_items"] == 1
    repository = NotificationRepository(paths["NOTIFICATIONS_DB"])
    technical_records = repository.list_notifications("tenant-local-studio-montagnese", "admin")
    assert len(technical_records) == 1
    assert technical_records[0].href == f"/notifiche-legali?presidio={presidio_id}"
    assert repository.list_notifications("studio-montagnese", "admin") == []


def test_materializzatore_pagina_oltre_200_senza_scadere_topbar_web_push_o_scadenze(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="PAGE-FASC-000",
        titolo="Presidio più vecchio da mantenere",
    )
    _seed_paginated_advanced_presidia(paths, range(1))
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    first = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )
    oldest_source_id = "legal-notification-presidio:page-presidio-000:da_preparare"
    oldest_marker = f"IUSENTRA_LEGAL_NOTIFICATION:{oldest_source_id}"
    notification_repository = NotificationRepository(paths["NOTIFICATIONS_DB"])
    assert first["advanced_items"] == 1
    assert (
        notification_repository.get_notification_by_dedupe_key(
            "tenant-test",
            "admin",
            oldest_source_id,
        )
        is not None
    )

    _seed_paginated_advanced_presidia(paths, range(1, 205))
    second = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert second["advanced_items"] == 205
    assert second["items"] == 205
    oldest_notification = notification_repository.get_notification_by_dedupe_key(
        "tenant-test",
        "admin",
        oldest_source_id,
    )
    assert oldest_notification is not None
    assert oldest_notification.expires_at == ""
    deadlines = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    active_deadlines = [
        item
        for item in deadlines
        if item.stato not in {StatoTermine.COMPLETATO, StatoTermine.ANNULLATO}
        and "IUSENTRA_LEGAL_NOTIFICATION:" in item.note
    ]
    assert len(active_deadlines) == 205
    assert any(oldest_marker in item.note for item in active_deadlines)
    assert second["calendar"]["completed"] == 0


def test_materializzatore_errore_repository_presidi_non_modifica_notifiche_o_scadenze(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    _seed_advanced_presidio(paths)
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )
    first = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )
    assert first["ok"] is True

    repository = NotificationRepository(paths["NOTIFICATIONS_DB"])
    before_notifications = [
        (item.id, item.source_id, item.read_at) for item in repository.list_notifications("tenant-test", "admin")
    ]
    before_deadlines = [
        (item.id, item.stato, item.note)
        for item in GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    ]

    def _repository_unavailable(*_args, **_kwargs):
        raise RuntimeError("Repository presidi temporaneamente non disponibile")

    monkeypatch.setattr(
        notifications_runtime,
        "_advanced_notification_repository_for_paths",
        _repository_unavailable,
    )

    with pytest.raises(RuntimeError, match="temporaneamente non disponibile"):
        notifications_runtime.materialize_notification_relata_presidio_for_paths(
            paths,
            tenant_label="studio-test",
            tenant_id="tenant-test",
        )

    after_notifications = [
        (item.id, item.source_id, item.read_at) for item in repository.list_notifications("tenant-test", "admin")
    ]
    after_deadlines = [
        (item.id, item.stato, item.note)
        for item in GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    ]
    assert after_notifications == before_notifications
    assert after_deadlines == before_deadlines


def test_materializzatore_archivio_pec_assente_fallisce_chiuso_senza_scadere_dati(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    _seed_advanced_presidio(paths)
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )
    first = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )
    assert first["ok"] is True

    repository = NotificationRepository(paths["NOTIFICATIONS_DB"])
    before_notifications = [
        (item.id, item.source_id, item.read_at) for item in repository.list_notifications("tenant-test", "admin")
    ]
    before_deadlines = [
        (item.id, item.stato, item.note)
        for item in GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    ]
    Path(paths["PEC_AUDIT_DB"]).unlink()

    with pytest.raises(
        notifications_runtime.NotificationRuntimeUnavailable,
        match="Archivio PEC_AUDIT_DB non disponibile",
    ):
        notifications_runtime.materialize_notification_relata_presidio_for_paths(
            paths,
            tenant_label="studio-test",
            tenant_id="tenant-test",
        )

    after_notifications = [
        (item.id, item.source_id, item.read_at) for item in repository.list_notifications("tenant-test", "admin")
    ]
    after_deadlines = [
        (item.id, item.stato, item.note)
        for item in GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    ]
    assert after_notifications == before_notifications
    assert after_deadlines == before_deadlines


def test_postgresql_senza_dsn_non_fallback_su_sqlite_o_json(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    database = _fake_postgres_database()
    NotificationPresidioRepository(paths["PEC_AUDIT_DB"], tenant_id="studio-postgresql")
    scadenziario = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"])
    scadenza = scadenziario.nuova(
        titolo="Presidio da non chiudere senza PostgreSQL",
        tipo=TipoTermine.NOTIFICA,
        data_scadenza="2026-07-22",
        note=("IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:presidio-pg:da_preparare\nPEC_AUDIT:pec-pg"),
        source_event_type="legal_notification_presidio",
    )
    scadenziario_path = Path(paths["SCADENZIARIO_DB"])
    before_scadenziario = scadenziario_path.read_bytes()
    notifications_path = Path(paths["NOTIFICATIONS_DB"])
    assert not notifications_path.exists()

    monkeypatch.setattr(
        notifications_runtime,
        "resolve_runtime_postgres_dsn",
        lambda **_kwargs: "",
    )
    monkeypatch.setattr(
        notifications_runtime,
        "_notification_fascicolo_rows",
        lambda *_args, **_kwargs: (0, 0, []),
    )
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    with pytest.raises(
        notifications_runtime.NotificationRuntimeUnavailable,
        match="Repository notifiche PostgreSQL",
    ):
        notifications_runtime.materialize_notification_relata_presidio_for_paths(
            paths,
            tenant_label="studio-postgresql",
            tenant_id="tenant-postgresql",
            presidio_tenant_id="studio-postgresql",
            database=database,
        )

    assert not notifications_path.exists()
    assert scadenziario_path.read_bytes() == before_scadenziario
    persisted = {
        item.id: item for item in GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    }
    assert persisted[scadenza.id].stato == StatoTermine.APERTO


def test_materializzatore_notifiche_residue_alimenta_topbar_push_e_scadenziario(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    NotificationPresidioRepository(paths["PEC_AUDIT_DB"], tenant_id="tenant-test")
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
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
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
    assert deadlines[0].id_fascicolo == "FNEW"
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


def test_materializzatore_presidi_pec_avanzati_alimenta_topbar_push_e_scadenziario(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    presidio_id = _seed_advanced_presidio(paths)
    presidio_repository = NotificationPresidioRepository(paths["PEC_AUDIT_DB"], tenant_id="tenant-test")
    try:
        presidio_repository.upsert_document(
            presidio_id,
            {
                "fascicolo_document_id": "DOC-ORIGINALE-PST",
                "document_role": "portal_original",
                "content_sha256": "f" * 64,
                "portal_document_id": "PST-DOC-ORIGINALE",
                "portal_reference": "PST-CAT-ORIGINALE",
                "original_filename": "sentenza-originale-pst.pdf",
                "authoritative": True,
            },
        )
    finally:
        presidio_repository.close()
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    report = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert report["ok"] is True
    assert report["scanned"] == 1
    assert report["advanced_items"] == 1
    assert report["items"] == 1
    assert report["to_notify"] == 1
    records = NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications("tenant-test", "admin")
    assert len(records) == 1
    assert records[0].source_type == "legal_notification_presidio"
    assert records[0].href == f"/notifiche-legali?presidio={presidio_id}"
    assert "Sentenza da valutare per la notifica" in records[0].title
    assert "Giuseppe Alfano" in records[0].title
    assert "Esamina la sentenza e conferma se procedere con la notifica" in records[0].body

    deadlines = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    assert len(deadlines) == 1
    assert deadlines[0].tipo == TipoTermine.NOTIFICA
    assert deadlines[0].stato == StatoTermine.APERTO
    assert deadlines[0].id_fascicolo == "C3565650"
    assert deadlines[0].note.splitlines() == [
        f"IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:{presidio_id}:da_preparare",
        "PEC_DOCUMENT_PRESIDIO:docpresidio:C3565650:DOC-ORIGINALE-PST:portal_original:linked",
        "PEC_AUDIT:pec_alfano",
        "Fonte documentale: sentenza-originale-pst.pdf",
    ]

    agenda_source = react_agenda_bridge._source_evidence(deadlines[0].note)
    assert agenda_source["sourceKind"] == "documento"
    assert agenda_source["sourceHref"] == (
        "/fascicoli/C3565650/documenti/DOC-ORIGINALE-PST/visualizza"
    )
    assert agenda_source["sourceLabel"] == "sentenza-originale-pst.pdf"

    scadenziario_source = react_scadenziario_bridge._source_evidence(deadlines[0])
    assert scadenziario_source["sourceKind"] == "documento"
    assert scadenziario_source["sourceHref"] == (
        "/fascicoli/C3565650/documenti/DOC-ORIGINALE-PST/visualizza"
    )
    assert scadenziario_source["sourceLabel"] == "sentenza-originale-pst.pdf"


def test_materializzatore_coalesce_legacy_sentenza_con_presidio_pec_autoritativo(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [
            {
                "id": "doc-sentenza-alfano",
                "nome": "19040620s.pdf",
                "tipo": "PROVVEDIMENTO",
                "classificazione_portale": "comunicazione_cancelleria",
                "note": "Sentenza ex art. 429 c.p.c. · PEC_AUDIT:pec_alfano",
                "data_documento": "2026-07-20",
            }
        ],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    # Il primo ciclo riproduce una proiezione legacy già pubblicata.
    NotificationPresidioRepository(paths["PEC_AUDIT_DB"], tenant_id="tenant-test")
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )
    first = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )
    assert first["items"] == 1
    first_deadline = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)[0]
    assert "IUSENTRA_LEGAL_NOTIFICATION:legal-notification:C3565650:da_preparare" in first_deadline.note

    presidio_id = _seed_advanced_presidio(paths)
    with sqlite3.connect(paths["PEC_AUDIT_DB"]) as conn:
        conn.execute(
            """
            UPDATE pec_legal_notification_documents
            SET original_filename='19040620s.pdf.zip'
            WHERE tenant_id='tenant-test' AND presidio_id=?
            """,
            (presidio_id,),
        )
    second = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert second["legacy_items"] == 1
    assert second["advanced_items"] == 1
    assert second["legacy_coalesced"] == 1
    assert second["items"] == 1
    assert second["to_notify"] == 1
    records = NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications(
        "tenant-test",
        "admin",
    )
    assert len(records) == 1
    assert records[0].href == f"/notifiche-legali?presidio={presidio_id}"

    all_deadlines = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    active_deadlines = [row for row in all_deadlines if row.stato == StatoTermine.APERTO]
    assert len(active_deadlines) == 1
    assert active_deadlines[0].note.splitlines() == [
        f"IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:{presidio_id}:da_preparare",
        "PEC_AUDIT:pec_alfano",
        "Fonte documentale: 19040620s.pdf.zip",
    ]
    legacy_deadline = next(row for row in all_deadlines if row.id == first_deadline.id)
    assert legacy_deadline.stato == StatoTermine.COMPLETATO
    assert second["calendar"]["completed"] == 1


def test_materializzatore_non_coalesce_fonti_distinte_nello_stesso_fascicolo_e_stadio(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [
            {
                "id": "doc-sentenza-diversa",
                "nome": "sentenza-diversa.pdf",
                "tipo": "PROVVEDIMENTO",
                "classificazione_portale": "comunicazione_cancelleria",
                "note": "Sentenza distinta · PEC_AUDIT:pec_sentenza_diversa",
                "data_documento": "2026-07-20",
            }
        ],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    _seed_advanced_presidio(paths)
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    report = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert report["legacy_items"] == 1
    assert report["advanced_items"] == 1
    assert report["legacy_coalesced"] == 0
    assert report["items"] == 2
    assert (
        len(
            NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications(
                "tenant-test",
                "admin",
            )
        )
        == 2
    )
    active_deadlines = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=True)
    assert len(active_deadlines) == 2


def test_materializzatore_non_pubblica_proof_deposited_ma_mantiene_proof_to_deposit(
    monkeypatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    presidio_id = _seed_advanced_presidio(paths)
    _advance_presidio_to_proof_to_deposit(paths, presidio_id)
    proof_marker = f"IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:{presidio_id}:ricevute_da_completare"
    manual_deadline = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).nuova(
        titolo="Deposita prova notifica",
        tipo=TipoTermine.NOTIFICA,
        data_scadenza="2026-07-21",
        note=f"{proof_marker}\nPEC_AUDIT:pec_alfano",
        source_event_type="legal_notification_presidio",
    )
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    first = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert first["advanced_items"] == 1
    assert first["to_notify"] == 0
    records = NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications("tenant-test", "admin")
    assert len(records) == 1
    assert records[0].source_id == f"legal-notification-presidio:{presidio_id}:ricevute_da_completare"
    deadlines = {
        item.id: item for item in GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    }
    assert deadlines[manual_deadline.id].stato == StatoTermine.APERTO

    _advance_presidio_to_proof_deposited(paths, presidio_id)
    second = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert second["advanced_items"] == 0
    assert second["items"] == 0
    assert NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications("tenant-test", "admin") == []
    closed = {item.id: item for item in GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)}
    assert closed[manual_deadline.id].stato == StatoTermine.COMPLETATO


def test_materializzatore_riconcilia_scaduti_e_sentenza_pec_storica(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    presidio_id = _seed_advanced_presidio(paths)
    scadenziario = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"])
    old_marker = scadenziario.nuova(
        titolo="Vecchio presidio notifica",
        tipo=TipoTermine.NOTIFICA,
        data_scadenza="2026-07-19",
        note="IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:old:da_preparare\nPEC_AUDIT:pec_old",
    )
    scadenziario.aggiorna(old_marker.id, stato=StatoTermine.SCADUTO)
    legacy_sentence = scadenziario.nuova(
        titolo="Sentenza da valutare per la notifica",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza="2025-04-09",
        note=(
            "PEC_AUDIT:pec_legacy\n"
            "Tipo evento: sentenza_da_valutare_per_notifica\n"
            "Attività per l'avvocato: esaminare la sentenza."
        ),
    )
    scadenziario.aggiorna(legacy_sentence.id, stato=StatoTermine.SCADUTO)
    extra_legacy_sentence = scadenziario.nuova(
        titolo="Sentenza da valutare per la notifica",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza="2026-07-20",
        note=(
            "PEC_AUDIT:pec_extra_legacy\n"
            "Tipo evento: sentenza_da_valutare_per_notifica\n"
            "Attività per l'avvocato: esaminare la sentenza."
        ),
    )
    scadenziario.aggiorna(extra_legacy_sentence.id, stato=StatoTermine.SCADUTO)
    active_marker = f"IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:{presidio_id}:da_preparare"
    completed_same_marker = scadenziario.nuova(
        titolo="Vecchio presidio stabile chiuso",
        tipo=TipoTermine.NOTIFICA,
        data_scadenza="2026-07-20",
        note=f"{active_marker}\nPEC_AUDIT:pec_alfano",
    )
    scadenziario.aggiorna(completed_same_marker.id, stato=StatoTermine.COMPLETATO)
    open_same_marker = scadenziario.nuova(
        titolo="Presidio stabile già aperto",
        tipo=TipoTermine.NOTIFICA,
        data_scadenza="2026-07-21",
        note=f"{active_marker}\nPEC_AUDIT:pec_alfano",
    )
    hearing = scadenziario.nuova(
        titolo="Udienza da PEC",
        tipo=TipoTermine.UDIENZA,
        data_scadenza="2026-09-09",
        note="PEC_AUDIT:pec_hearing\nTipo evento: fissazione_udienza",
    )
    scadenziario.aggiorna(hearing.id, stato=StatoTermine.SCADUTO)
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    report = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert report["calendar"]["completed"] == 3
    deadlines = {
        item.id: item for item in GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    }
    assert deadlines[old_marker.id].stato == StatoTermine.COMPLETATO
    assert deadlines[legacy_sentence.id].stato == StatoTermine.COMPLETATO
    assert deadlines[extra_legacy_sentence.id].stato == StatoTermine.COMPLETATO
    assert deadlines[completed_same_marker.id].stato == StatoTermine.COMPLETATO
    assert deadlines[open_same_marker.id].stato == StatoTermine.APERTO
    assert "Storico sentenze PEC riconciliato" in deadlines[legacy_sentence.id].note
    assert deadlines[hearing.id].stato == StatoTermine.SCADUTO
    current = [
        item for item in deadlines.values() if active_marker in item.note and item.stato != StatoTermine.COMPLETATO
    ]
    assert len(current) == 1
    assert current[0].id == open_same_marker.id


def test_materializzatore_riapre_marker_attivo_se_resta_solo_scadenza_terminale(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    presidio_id = _seed_advanced_presidio(paths)
    active_marker = f"IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:{presidio_id}:da_preparare"
    scadenziario = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"])
    terminal = scadenziario.nuova(
        titolo="Vecchia riga stabile già chiusa",
        tipo=TipoTermine.NOTIFICA,
        data_scadenza="2026-07-20",
        note=f"{active_marker}\nPEC_AUDIT:pec_alfano",
    )
    scadenziario.aggiorna(terminal.id, stato=StatoTermine.COMPLETATO)
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    first = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )
    second = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert first["calendar"]["created"] == 1
    assert second["calendar"]["created"] == 0
    assert second["calendar"]["updated"] == 1
    deadlines = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    active = [
        item
        for item in deadlines
        if active_marker in item.note and item.stato not in {StatoTermine.COMPLETATO, StatoTermine.ANNULLATO}
    ]
    assert len(active) == 1
    assert active[0].tipo == TipoTermine.NOTIFICA
    assert active[0].id != terminal.id


def test_materializzatore_non_usa_studio_db_come_mirror_scadenziario(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    NotificationPresidioRepository(paths["PEC_AUDIT_DB"], tenant_id="tenant-test")
    StudioDB.get(paths["STUDIO_DB"]).ensure_schema()
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [
            {
                "id": "doc-1",
                "nome": "Sentenza da valutare per notifica.pdf",
                "tipo": "SENTENZA",
                "classificazione_portale": "comunicazione_cancelleria",
                "note": "Sentenza da valutare per la notifica.",
                "data_documento": "2026-07-20",
            }
        ],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    paths["SCADENZIARIO_DB"] = paths["STUDIO_DB"]
    studio_db = Path(paths["STUDIO_DB"])
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    report = notifications_runtime.materialize_notification_relata_presidio_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
    )

    assert report["calendar"]["created"] == 1
    assert studio_db.read_bytes()[:16] == b"SQLite format 3\x00"
    with sqlite3.connect(str(studio_db)) as conn:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM scadenze").fetchone()[0] == 1
    mirror = studio_db.parent / "scadenziario" / "scadenze.json"
    assert mirror.exists()
    assert json.loads(mirror.read_text(encoding="utf-8"))


def test_materializzatore_campione_pubblica_solo_i_presidi_pec_selezionati(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    presidio_id = _seed_advanced_presidio(paths)
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    report = notifications_runtime.materialize_selected_advanced_notification_presidia_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
        presidio_ids=[presidio_id],
    )

    assert report["ok"] is True
    assert report["selected"] == 1
    assert report["items"] == 1
    records = NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications("tenant-test", "admin")
    assert len(records) == 1
    assert "Sentenza da valutare per la notifica" in records[0].title
    deadlines = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)
    assert len(deadlines) == 1
    assert deadlines[0].stato == StatoTermine.APERTO

    no_result = notifications_runtime.materialize_selected_advanced_notification_presidia_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
        presidio_ids=["non-esiste"],
    )
    assert no_result["ok"] is False
    assert (
        GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"]).tutte(solo_aperte=False)[0].stato == StatoTermine.APERTO
    )


def test_materializzatore_campione_scade_solo_il_presidio_sostituito(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_fascicolo(
        Path(paths["STUDIO_DB"]),
        [],
        fascicolo_id="C3565650",
        titolo="Carta docente - MIM",
        nome_cliente="Giuseppe Alfano",
        numero_rg="1100",
        anno_rg="2026",
    )
    presidio_id = _seed_advanced_presidio(paths)
    repository = NotificationRepository(paths["NOTIFICATIONS_DB"])
    stale_id = "presidio-duplicato"
    repository.upsert_notification(
        NotificationRecord(
            tenant_id="tenant-test",
            user_id="admin",
            type="operational",
            title="Doppione da non mostrare",
            body="Presidio sostituito.",
            source_type="legal_notification_presidio",
            source_id=f"legal-notification-presidio:{stale_id}:da_preparare",
            dedupe_key=f"legal-notification-presidio:{stale_id}:da_preparare",
        )
    )
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *_args, **_kwargs: [SimpleNamespace(id="admin", username="admin", ha_permesso=lambda _permission: True)],
    )

    report = notifications_runtime.materialize_selected_advanced_notification_presidia_for_paths(
        paths,
        tenant_label="studio-test",
        tenant_id="tenant-test",
        presidio_ids=[presidio_id],
        superseded_presidio_ids=[stale_id],
    )

    assert report["expired_superseded"] == 1
    records = repository.list_notifications("tenant-test", "admin")
    assert len(records) == 1
    assert "Doppione" not in records[0].title
