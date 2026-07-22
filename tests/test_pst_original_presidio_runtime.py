from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from flask import Flask

from pct.pec_notification_presidio import (
    NotificationPresidioRepository,
    NotificationPresidioService,
    PresidioStatus,
)
from web.services import notifications_runtime
from web.services.pst_original_presidio_runtime import (
    link_existing_pst_originals_from_fascicolo,
    register_imported_pst_originals,
)
from web.bootstrap.portali_acquisizione_routes import register_portali_acquisizione_routes


def _repository(tmp_path: Path, tenant_id: str = "studio-legale-giuseppe-montagnese") -> NotificationPresidioRepository:
    return NotificationPresidioRepository(tmp_path / "pec_audit.sqlite", tenant_id=tenant_id)


def _seed_presidio(
    repository: NotificationPresidioRepository,
    *,
    fascicolo_id: str = "FASC-MONTAGNESE",
    source_message_id: str = "pec-montagnese",
    filename: str = "sentenza.pdf",
    content_sha256: str = "a" * 64,
) -> str:
    result = NotificationPresidioService(repository).create_candidate(
        {
            "fascicolo_id": fascicolo_id,
            "source_message_id": source_message_id,
            "source_order_or_event_id": source_message_id,
            "source_effective_at": "2026-07-22T10:00:00+02:00",
            "trigger_type": "STRATEGIC_NOTIFICATION_REVIEW",
            "notification_case": "judgment_to_notify_review",
            "rulepack_version": "pytest-pst-original",
            "priority": "P1",
            "confidence": 0.99,
            "live_pec_operational_event": True,
            "detection_reason": "Sentenza da verificare per la notifica.",
            "documents": [
                {
                    "content_sha256": content_sha256,
                    "original_filename": filename,
                    "document_version": "1",
                    "document_role": "office_pec_copy",
                    "authoritative": False,
                }
            ],
            "recipients": [
                {
                    "name": "Ministero dell'Istruzione e del Merito",
                    "role": "controparte",
                    "required": True,
                }
            ],
        }
    )
    return str(result["id"])


def _imported_original(
    *,
    document_id: str = "DOC-ORIGINALE",
    filename: str = "sentenza.pdf.p7m",
    content_sha256: str = "a" * 64,
) -> dict[str, Any]:
    return {
        "fascicolo_document_id": document_id,
        "nome": filename,
        "nome_originale": filename,
        "hash_sha256": content_sha256,
        "id_documento_portale": "PST-DOC-001",
        "id_cat_portale": "PST-CAT-001",
        "modalita_documento_portale": "originale",
        "original_documento_portale": True,
    }


def test_originale_pst_univoco_collega_documento_transizione_e_proiezione(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    presidio_id = _seed_presidio(repository)
    projector_calls: list[dict[str, Any]] = []

    report = register_imported_pst_originals(
        repository,
        fascicolo_id="FASC-MONTAGNESE",
        imported_documents=[_imported_original()],
        actor="avvocato-montagnese",
        target_document={"pecId": "pec-montagnese"},
        projector=lambda **kwargs: projector_calls.append(kwargs) or {"ok": True},
    )

    assert report["ok"] is True
    assert report["collegati"] == [
        {
            "presidio_id": presidio_id,
            "fascicolo_document_id": "DOC-ORIGINALE",
            "document_role": "portal_original",
            "authoritative": True,
            "identity_key": report["collegati"][0]["identity_key"],
            "correlation_reason": "correlazione_univoca_fascicolo",
            "previous_status": "DETECTED",
            "status": "ORIGINAL_ACQUIRED",
            "transitioned": True,
            "newly_linked": True,
        }
    ]
    assert projector_calls == [
        {
            "presidio_ids": [presidio_id],
            "redispatch_presidio_ids": [presidio_id],
        }
    ]
    assert repository.get_presidio(presidio_id)["status"] == PresidioStatus.ORIGINAL_ACQUIRED.value
    with repository.connection() as conn:
        document = dict(
            conn.execute(
                """
                SELECT * FROM pec_legal_notification_documents
                WHERE tenant_id=? AND presidio_id=? AND document_role='portal_original'
                """,
                (repository.tenant_id, presidio_id),
            ).fetchone()
        )
        evidence_count = conn.execute(
            """
            SELECT COUNT(*) FROM pec_legal_notification_evidence
            WHERE tenant_id=? AND presidio_id=? AND evidence_key LIKE 'pst-portal-original:%'
            """,
            (repository.tenant_id, presidio_id),
        ).fetchone()[0]
    assert document["fascicolo_document_id"] == "DOC-ORIGINALE"
    assert bool(document["authoritative"]) is True
    assert evidence_count == 1

    repeated = register_imported_pst_originals(
        repository,
        fascicolo_id="FASC-MONTAGNESE",
        imported_documents=[_imported_original()],
        actor="avvocato-montagnese",
        target_document={"pecId": "pec-montagnese"},
        projector=lambda **kwargs: projector_calls.append(kwargs) or {"ok": True},
    )

    assert repeated["ok"] is True
    assert repeated["collegati"][0]["newly_linked"] is False
    assert repeated["collegati"][0]["transitioned"] is False
    assert len(projector_calls) == 1
    with repository.connection() as conn:
        assert (
            conn.execute(
                """
            SELECT COUNT(*) FROM pec_legal_notification_documents
            WHERE tenant_id=? AND presidio_id=? AND document_role='portal_original'
            """,
                (repository.tenant_id, presidio_id),
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                """
            SELECT COUNT(*) FROM pec_legal_notification_transitions
            WHERE tenant_id=? AND presidio_id=? AND next_status='ORIGINAL_ACQUIRED'
            """,
                (repository.tenant_id, presidio_id),
            ).fetchone()[0]
            == 1
        )


def test_originale_pst_non_fa_regredire_un_presidio_gia_confermato(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    presidio_id = _seed_presidio(repository, content_sha256="b" * 64)
    repository.transition(
        presidio_id,
        PresidioStatus.NOTIFICATION_CONFIRMED,
        actor="avvocato-montagnese",
        reason="Notifica necessaria confermata dopo la verifica del provvedimento.",
        evidence={"source": "pytest"},
        idempotency_key="pytest-conferma-notifica",
    )
    projector_calls: list[dict[str, Any]] = []

    report = register_imported_pst_originals(
        repository,
        fascicolo_id="FASC-MONTAGNESE",
        imported_documents=[_imported_original(content_sha256="b" * 64)],
        actor="avvocato-montagnese",
        target_document={"pecId": "pec-montagnese"},
        projector=lambda **kwargs: projector_calls.append(kwargs) or {"ok": True},
    )

    assert report["ok"] is True
    assert report["collegati"][0]["previous_status"] == "NOTIFICATION_CONFIRMED"
    assert report["collegati"][0]["status"] == "NOTIFICATION_CONFIRMED"
    assert report["collegati"][0]["transitioned"] is False
    assert projector_calls[0]["redispatch_presidio_ids"] == [presidio_id]


def test_originale_pst_ambiguo_non_viene_collegato_arbitrariamente(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    first = _seed_presidio(
        repository,
        source_message_id="pec-prima",
        filename="prima-sentenza.pdf",
        content_sha256="c" * 64,
    )
    second = _seed_presidio(
        repository,
        source_message_id="pec-seconda",
        filename="seconda-sentenza.pdf",
        content_sha256="d" * 64,
    )

    report = register_imported_pst_originals(
        repository,
        fascicolo_id="FASC-MONTAGNESE",
        imported_documents=[
            _imported_original(
                filename="provvedimento-senza-riferimento.pdf",
                content_sha256="e" * 64,
            )
        ],
        actor="avvocato-montagnese",
    )

    assert report["ok"] is False
    assert report["collegati"] == []
    assert report["saltati"] == [{"reason": "correlazione_ambigua"}]
    assert repository.get_presidio(first)["status"] == "DETECTED"
    assert repository.get_presidio(second)["status"] == "DETECTED"


def test_presidio_riconosce_provvedimento_pst_gia_presente_nel_fascicolo(monkeypatch, tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    presidio_id = _seed_presidio(
        repository,
        fascicolo_id="78D6022C",
        source_message_id="pec_d23c133a4ef8ada88ecb8c08",
        filename="9732730s.pdf.zip",
        content_sha256="f" * 64,
    )
    fascicolo = SimpleNamespace(
        documenti=[
            SimpleNamespace(
                id="DE29EE7F",
                nome="SentenzaDefinitiva_35882174.pdf",
                nome_originale="SentenzaDefinitiva_35882174.pdf",
                nome_portale="SentenzaDefinitiva_35882174.pdf",
                tipo="SENTENZA",
                tipo_atto_portale="SentenzaDefinitiva",
                classificazione_portale="SentenzaDefinitiva",
                id_documento_portale="35882174",
                id_cat_portale="35882174",
                hash_sha256="ea33441ec44017f7b7525e52fda19b4f29d030bccac0afe6cc248b12b189a2da",
                note="Importato da PolisWeb / PST il 22/07/2026 | Origine: pst:JPW_SIL_DISTR:35882174 | Tipo atto portale: SentenzaDefinitiva",
                tags=["Documenti fascicolo", "SentenzaDefinitiva", "Copia di consultazione"],
            ),
            SimpleNamespace(
                id="RICORSO-1",
                nome="Ricorso introduttivo.pdf",
                nome_originale="Ricorso introduttivo.pdf",
                tipo="RICORSO",
                tipo_atto_portale="Ricorso",
                id_documento_portale="111",
                id_cat_portale="111",
                note="Importato da PolisWeb / PST il 20/05/2026 | Origine: pst:JPW_SIL_DISTR:111",
                tags=["Documenti fascicolo", "Ricorso"],
            ),
        ]
    )
    import web.helpers

    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: SimpleNamespace(get=lambda identifier: fascicolo if identifier == "78D6022C" else None))

    report = link_existing_pst_originals_from_fascicolo(
        repository,
        presidio=repository.get_presidio(presidio_id),
        actor="sistema",
        portal_context={"tipo_documento": "sentenza"},
        projector=lambda **kwargs: {"ok": True, "kwargs": kwargs},
    )

    assert report["ok"] is True
    assert report["collegati"][0]["fascicolo_document_id"] == "DE29EE7F"
    assert report["collegati"][0]["document_role"] == "portal_original"
    assert report["collegati"][0]["newly_linked"] is True
    assert report["collegati"][0]["status"] == "ORIGINAL_ACQUIRED"
    with repository.connection() as conn:
        rows = conn.execute(
            """
            SELECT fascicolo_document_id, document_role, original_filename, portal_document_id
            FROM pec_legal_notification_documents
            WHERE tenant_id=? AND presidio_id=? AND document_role='portal_original'
            """,
            (repository.tenant_id, presidio_id),
        ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "fascicolo_document_id": "DE29EE7F",
            "document_role": "portal_original",
            "original_filename": "SentenzaDefinitiva_35882174.pdf",
            "portal_document_id": "35882174",
        }
    ]


class _FakeNotificationRepository:
    def __init__(self, current_source_id: str) -> None:
        self.current_source_id = current_source_id
        self.expired_source_ids: set[str] = set()

    def get_notification_by_dedupe_key(self, tenant_id: str, user_id: str, dedupe_key: str):
        if dedupe_key != self.current_source_id:
            return None
        return SimpleNamespace(
            id="NOTIFICATION-1",
            tenant_id=tenant_id,
            user_id=user_id,
            priority="important",
        )

    def expire_notifications_by_source_ids(
        self,
        tenant_id: str,
        user_id: str,
        *,
        source_type: str,
        source_ids: set[str],
    ) -> int:
        self.expired_source_ids.update(source_ids)
        return len(source_ids)


class _FakeNotificationService:
    instance: "_FakeNotificationService | None" = None

    def __init__(self, repository: _FakeNotificationRepository, **_kwargs: Any) -> None:
        self.repository = repository
        self.synced_items: list[dict[str, Any]] = []
        self.push_dispatches = 0
        self.__class__.instance = self

    def sync_operational_items(self, *, items: list[dict[str, Any]], **_kwargs: Any) -> list[Any]:
        self.synced_items = list(items)
        return []

    def dispatch_web_push(self, _record: Any) -> SimpleNamespace:
        self.push_dispatches += 1
        return SimpleNamespace(attempted=1, sent=1)


def test_materializzazione_mirata_unifica_stato_e_usa_solo_scadenziario(monkeypatch) -> None:
    presidio_id = "PRESIDIO-MONTAGNESE"
    fascicolo_id = "FASC-MONTAGNESE"
    current_source_id = f"legal-notification-presidio:{presidio_id}:da_preparare"
    item = {
        "id": current_source_id,
        "fascicoloId": fascicolo_id,
        "type": notifications_runtime.LEGAL_NOTIFICATION_SOURCE_TYPE,
        "priority": "important",
        "title": "Notifica legale da presidiare",
        "message": "Originale acquisito; prepara la relata.",
        "href": f"/notifiche-legali?presidio={presidio_id}",
    }
    repository = _FakeNotificationRepository(current_source_id)
    deadline_call: dict[str, Any] = {}
    monkeypatch.setattr(notifications_runtime, "_advanced_notification_items", lambda *args, **kwargs: [item])
    monkeypatch.setattr(notifications_runtime, "_core_fascicolo_rows", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        notifications_runtime,
        "notification_recipients_for_paths",
        lambda *args, **kwargs: [SimpleNamespace(id="UTENTE-MONTAGNESE")],
    )
    monkeypatch.setattr(
        notifications_runtime,
        "build_notification_repository_for_paths",
        lambda *args, **kwargs: repository,
    )
    monkeypatch.setattr(notifications_runtime, "NotificationService", _FakeNotificationService)
    monkeypatch.setattr(notifications_runtime, "load_web_push_config", lambda *_args, **_kwargs: object())

    def _deadlines(_paths, items, **kwargs):
        deadline_call.update({"items": items, **kwargs})
        return {"created": 0, "updated": 1, "completed": 1}

    monkeypatch.setattr(notifications_runtime, "_sync_legal_notification_deadlines", _deadlines)

    report = notifications_runtime.materialize_selected_advanced_notification_presidia_for_paths(
        {"_TENANT_NOTIFICATION_ID": "tenant-uuid-montagnese"},
        tenant_label="studio-legale-giuseppe-montagnese",
        tenant_id="tenant-uuid-montagnese",
        presidio_tenant_id="studio-legale-giuseppe-montagnese",
        presidio_ids=[presidio_id],
        superseded_presidio_ids=[presidio_id],
        redispatch_presidio_ids=[presidio_id],
    )

    service = _FakeNotificationService.instance
    assert report["ok"] is True
    assert report["redispatched_pushes"] == 1
    assert service is not None and service.push_dispatches == 1
    assert service.synced_items == [item]
    assert current_source_id not in repository.expired_source_ids
    assert f"legal-notification-presidio:{presidio_id}:da_acquisire" in repository.expired_source_ids
    assert deadline_call["reconcile_existing"] is True
    assert (
        f"IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:{presidio_id}:"
        in deadline_call["reconcile_source_prefixes"]
    )
    assert "AGENDA_DB" not in deadline_call


def test_import_e_importa_payload_inoltrano_sempre_il_target_document() -> None:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="pytest")
    captured: list[dict[str, Any]] = []

    def _importer(
        _portale: str,
        _selection: dict[str, Any],
        _preview: dict[str, Any],
        _options: dict[str, Any],
        _mapping: dict[str, Any],
        *,
        downloaded_files: list[dict[str, Any]],
        target_document: dict[str, Any],
    ) -> dict[str, Any]:
        captured.append(
            {
                "downloaded_files": downloaded_files,
                "target_document": target_document,
            }
        )
        return {"id_fascicolo": "FASC-MONTAGNESE"}

    normalized = {
        "selection": {"numero": "1428", "anno": "2026"},
        "preview": {"counts": {"documenti": 1}},
    }
    register_portali_acquisizione_routes(
        app,
        get_fascicoli=lambda: SimpleNamespace(get=lambda _identifier: None),
        _spec_portale_acquisizione=lambda _portale: {},
        _pdp_penale_workspace_url_for_fascicolo=lambda _identifier: "",
        _build_access_status_payload=lambda _portale: {},
        _search_fascicoli_portale_server=lambda _portale, _query: [],
        _annotate_portale_search_rows=lambda _portale, rows: rows,
        _preview_documenti_portale_server=lambda _portale, _selection: [],
        _build_portale_preview=lambda _portale, _selection, documents: {
            "documenti": documents
        },
        _coerce_import_options=lambda options, **_kwargs: options,
        _coerce_mapping=lambda mapping: mapping,
        _analyze_portale_import=lambda *_args, **_kwargs: {},
        _normalize_authorized_portale_payload=lambda _portale, _payload: normalized,
        _importa_o_collega_fascicolo_portale=_importer,
        _importa_file_assistiti_portale=lambda *_args, **_kwargs: {},
        _portal_assistant_start=lambda *_args, **_kwargs: {},
        _portal_assistant_open=lambda *_args, **_kwargs: {},
        _portal_assistant_watch_downloads=lambda *_args, **_kwargs: {},
        _portal_assistant_status=lambda *_args, **_kwargs: {},
        _portal_assistant_collect=lambda *_args, **_kwargs: {},
        _portal_assistant_close=lambda *_args, **_kwargs: {},
        _deposito_precheck_assistito=lambda *_args, **_kwargs: {},
        _deposito_prepara_assistito=lambda *_args, **_kwargs: {},
        _deposito_assistant_start=lambda *_args, **_kwargs: {},
        _deposito_importa_ricevute_assistito=lambda *_args, **_kwargs: {},
        _deposito_finalizza_assistito=lambda *_args, **_kwargs: {},
    )
    target = {
        "singleDocument": True,
        "pecId": "pec-montagnese",
        "idDocumento": "PST-DOC-001",
        "hash": "A" * 64,
    }
    direct_payload = {
        **normalized,
        "target_document": target,
        "downloaded_files": [{"nome": "sentenza.pdf"}],
    }
    authorized_payload = {
        "payload": {"fascicolo": {"numero": "1428"}},
        "target_document": target,
        "downloaded_files": [{"nome": "sentenza.pdf.p7m"}],
    }

    with app.test_client() as client:
        direct = client.post("/api/portali/pst/acquisizione/import", json=direct_payload)
        authorized = client.post(
            "/api/portali/pst/acquisizione/importa-payload",
            json=authorized_payload,
        )

    assert direct.status_code == 200 and direct.get_json()["ok"] is True
    assert authorized.status_code == 200 and authorized.get_json()["ok"] is True
    assert [row["target_document"] for row in captured] == [
        {
            "singleDocument": True,
            "documento": "",
            "idDocumento": "PST-DOC-001",
                "hash": "a" * 64,
                "pecId": "pec-montagnese",
                "tipoDocumento": "",
        },
        {
            "singleDocument": True,
            "documento": "",
            "idDocumento": "PST-DOC-001",
                "hash": "a" * 64,
                "pecId": "pec-montagnese",
                "tipoDocumento": "",
        },
    ]
