"""Presidio PEC automatico: acquisizione incrementale dall'archivio locale.

La sincronizzazione caselle archivia le PEC; il presidio automatico dello
scheduler deve acquisirle nella pipeline (classificazione, scadenze, link
fascicolo) senza azioni manuali e senza riacquisire ciò che è già presidiato.
"""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from pct.email_client import CartellaEmail, EmailRicevuta, GestioneEmailRicevute, StatoEmail
from web.services.pec_pipeline_runtime import (
    acquire_local_pec_for_paths,
    repository_from_paths,
)
from web.services import pec_pipeline_runtime


def _paths(tmp_path: Path) -> dict[str, str]:
    return {
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "PEC_AUDIT_DB": str(tmp_path / "email" / "pec_audit.sqlite"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
    }


def _pec_mime(message_id: str, subject: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = "posta-certificata@legalmail.it"
    msg["To"] = "studio@example.pec.it"
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    msg.set_content(f"Messaggio di posta certificata. {subject}.")
    msg.add_attachment(
        b"<daticert><msgid>auto-acquire</msgid></daticert>",
        maintype="application",
        subtype="xml",
        filename="daticert.xml",
    )
    return msg.as_bytes()


def _archivia_pec(
    gestore: GestioneEmailRicevute,
    *,
    email_id: str,
    message_id: str,
    subject: str,
    with_eml: bool = True,
    data: str = "",
) -> None:
    eml_file = ""
    eml_sha = ""
    if with_eml:
        eml_info = gestore._salva_eml_originale(email_id, _pec_mime(message_id, subject))  # noqa: SLF001
        eml_file = eml_info["eml_file"]
        eml_sha = eml_info["eml_sha256"]
    gestore.aggiungi(
        EmailRicevuta(
            id=email_id,
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="Per conto di: tribunale.palmi@civile.ptel.giustiziacert.it",
            destinatari="studio@example.pec.it",
            oggetto=subject,
            data=data,
            corpo_testo=f"Messaggio di posta certificata. {subject}.",
            message_id=message_id,
            allegati=[{"nome": "daticert.xml", "mime": "application/xml", "size": 48}],
            eml_file=eml_file,
            eml_sha256=eml_sha,
        )
    )


def _archivia_email_ordinaria(gestore: GestioneEmailRicevute, *, email_id: str) -> None:
    gestore.aggiungi(
        EmailRicevuta(
            id=email_id,
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="newsletter@example.com",
            destinatari="studio@example.com",
            oggetto="Saluti dallo staff",
            corpo_testo="Contenuto ordinario senza marcatori certificati.",
        )
    )


def test_acquisizione_automatica_ingerisce_solo_pec_nuove(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    gestore = GestioneEmailRicevute(paths["EMAIL_CASELLA_DB"])
    _archivia_pec(
        gestore,
        email_id="MAIL-AUTO-1",
        message_id="<auto-acquire-1@example.test>",
        subject="POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO RG: 12/2026",
    )
    _archivia_email_ordinaria(gestore, email_id="MAIL-ORDINARIA")

    first = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=10)
    assert first["relevant"] == 1
    assert first["ingested"] == 1
    assert first["errors"] == 0

    repo = repository_from_paths(paths, tenant_label="default")
    workers = repo.run_pending_jobs(limit=30, actor="pytest")
    assert workers["processed"] >= 1, "i job accodati dall'acquisizione devono essere lavorati"
    assert workers["failed"] == 0

    second = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=10)
    assert second["ingested"] == 0, "una PEC già presidiata non va riacquisita"
    assert second["scan_mode"] in {"incremental", "incremental_backlog"}
    assert second["scanned"] <= first["scanned"]


def test_acquisizione_automatica_non_ritenta_le_missing_mime(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    gestore = GestioneEmailRicevute(paths["EMAIL_CASELLA_DB"])
    _archivia_pec(
        gestore,
        email_id="MAIL-SENZA-EML",
        message_id="",
        subject="POSTA CERTIFICATA: comunicazione di cancelleria",
        with_eml=False,
    )

    first = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=10)
    assert first["missing_mime"] in {0, 1}
    if first["missing_mime"] == 0:
        # MIME ricostruito dall'archivio: la PEC entra comunque nel presidio.
        assert first["ingested"] == 1
    second = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=10)
    assert second["ingested"] == 0
    assert second["scan_mode"] in {"incremental", "incremental_backlog"}
    assert second["scanned"] <= first["scanned"], "l'esito registrato evita nuovi tentativi a ogni giro"


def test_acquisizione_rispetta_il_budget_per_giro(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    gestore = GestioneEmailRicevute(paths["EMAIL_CASELLA_DB"])
    for index in range(3):
        _archivia_pec(
            gestore,
            email_id=f"MAIL-BUDGET-{index}",
            message_id=f"<auto-budget-{index}@example.test>",
            subject=f"POSTA CERTIFICATA: comunicazione {index}",
        )

    first = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=2)
    assert first["ingested"] == 2, "il budget per giro deve essere rispettato"
    second = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=2)
    assert second["ingested"] == 1, "il giro successivo completa l'arretrato"
    assert second["skipped_presided"] == 2


def test_acquisizione_full_scan_marca_le_pec_gia_presidiate(tmp_path: Path, monkeypatch) -> None:
    paths = _paths(tmp_path)
    gestore = GestioneEmailRicevute(paths["EMAIL_CASELLA_DB"])
    _archivia_pec(
        gestore,
        email_id="MAIL-GIA-PRESIDIATA",
        message_id="<gia-presidiata@example.test>",
        subject="POSTA CERTIFICATA: comunicazione già presidiata",
    )

    first = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=10)
    monkeypatch.setenv("IUSENTRA_PEC_AUTO_ACQUIRE_FULL_SCAN", "1")
    second = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=10)

    index = repository_from_paths(paths, tenant_label="default").local_acquire_presidio_index()
    assert first["ingested"] == 1
    assert second["skipped_presided"] == 1
    assert index["by_email_id"]["MAIL-GIA-PRESIDIATA"]["status"] == "already_presided"


def test_acquisizione_incrementale_legge_solo_nuovi_arrivi_dopo_cursor(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    gestore = GestioneEmailRicevute(paths["EMAIL_CASELLA_DB"])
    _archivia_pec(
        gestore,
        email_id="MAIL-CURSOR-1",
        message_id="<cursor-1@example.test>",
        subject="POSTA CERTIFICATA: primo arrivo",
        data="2026-06-25T10:00:00",
    )
    _archivia_pec(
        gestore,
        email_id="MAIL-CURSOR-2",
        message_id="<cursor-2@example.test>",
        subject="POSTA CERTIFICATA: secondo arrivo",
        data="2026-06-25T10:05:00",
    )

    first = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=10)
    assert first["ingested"] == 2
    assert first["cursor_saved"] is True

    second = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=10)
    assert second["scan_mode"] == "incremental"
    assert second["ingested"] == 0
    assert second["scanned"] < first["archive_seen"], "dopo il cursore non deve rileggere tutta la casella"

    _archivia_pec(
        gestore,
        email_id="MAIL-CURSOR-3",
        message_id="<cursor-3@example.test>",
        subject="POSTA CERTIFICATA: nuovo arrivo",
        data="2026-06-25T10:10:00",
    )

    third = acquire_local_pec_for_paths(paths, tenant_label="default", batch_size=10)
    assert third["scan_mode"] == "incremental"
    assert third["ingested"] == 1
    assert third["relevant"] <= 2, "il giro nuovo controlla arrivo e boundary, non l'archivio intero"


def test_worker_pec_rispetta_budget_documentale_scheduler(tmp_path: Path, monkeypatch) -> None:
    paths = _paths(tmp_path)
    recovered_limits: list[int] = []

    class FakeRepository:
        def enqueue_stale_attachment_repairs(self, *, limit: int, actor: str) -> dict[str, object]:
            return {"ok": True, "queued": 1, "unresolved": 0, "limit": limit, "actor": actor}

        def run_pending_jobs(self, *, limit: int, actor: str) -> dict[str, object]:
            return {"processed": 0, "failed": 0, "jobs": [], "limit": limit, "actor": actor}

        def cleanup_legacy_pec_operational_items(self, *, actor: str) -> dict[str, int]:
            return {"scadenziario_removed": 0, "agenda_removed": 0, "errors": 0}

        def recover_missing_hearings_from_fascicolo_documents(self, *, limit: int, actor: str) -> dict[str, int]:
            recovered_limits.append(limit)
            return {"checked_fascicoli": limit, "checked_documents": limit * 2, "scheduled": 0, "already_presided": 0}

    monkeypatch.setattr(
        pec_pipeline_runtime,
        "repository_from_paths",
        lambda _paths, *, tenant_label: FakeRepository(),
    )

    report = pec_pipeline_runtime.run_workers_for_paths(
        paths,
        tenant_label="default",
        limit=60,
        document_presidio_limit=5,
    )
    assert recovered_limits == [5]
    assert report["attachment_maintenance"]["queued"] == 1
    assert report["document_presidio"]["checked_fascicoli"] == 5

    skipped = pec_pipeline_runtime.run_workers_for_paths(
        paths,
        tenant_label="default",
        limit=60,
        document_presidio_limit=0,
    )
    assert recovered_limits == [5], "limite 0: il presidio documentale non deve partire"
    assert skipped["document_presidio"]["reason"] == "budget_scheduler_esaurito"


def test_notifica_scadenze_automatiche_agli_utenti_dello_studio(tmp_path: Path) -> None:
    from flask import Flask

    from pct.auth import GestioneUtenti
    from pct.notifications import NotificationRepository
    from web.services.pec_pipeline_runtime import notify_auto_deadlines_for_paths

    paths = _paths(tmp_path)
    paths["AUTH_DB"] = str(tmp_path / "auth" / "utenti.json")
    paths["AUDIT_DB"] = str(tmp_path / "auth" / "audit.json")
    paths["NOTIFICATIONS_DB"] = str(tmp_path / "notifications" / "notifications.db")
    # L'admin di bootstrap è l'utente attivo dello studio destinatario.
    GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test-secret",
        bootstrap_admin_credentials_path=str(tmp_path / "auth" / "bootstrap_admin.json"),
    )

    remote_url = "https://teams.microsoft.com/l/meetup-join/udienza-auto?context=%7B%22Tid%22%3A%22123%22%7D"
    jobs = [
        {
            "job_type": "link",
            "message_id": "pec_msg_auto_1",
            "result": {
                "auto_deadline": {
                    "ok": True,
                    "deadline_id": "SCAD-1",
                    "due_date": "2026-07-01",
                    "agenda": {"agenda_id": "AG-1", "agenda_href": "/agenda/AG-1"},
                    "proposal": {
                        "remote_hearing": {
                            "detected": True,
                            "mode": "audiovisiva",
                            "links": [
                                {
                                    "url": remote_url,
                                    "source": "decreto-udienza.pdf.zip",
                                    "exact_match": True,
                                }
                            ],
                        }
                    },
                }
            },
        },
        {"job_type": "parse", "message_id": "pec_msg_auto_1", "result": {}},
    ]

    app = Flask(__name__)
    app.secret_key = "test-secret"
    with app.app_context():
        first = notify_auto_deadlines_for_paths(paths, tenant_label="default", jobs=jobs)
        second = notify_auto_deadlines_for_paths(paths, tenant_label="default", jobs=jobs)

    assert first["recipients"] >= 1
    assert first["created"] == first["recipients"], "una notifica per ogni utente attivo"
    assert first["errors"] == 0
    assert second["created"] == 0, "stessa scadenza: la dedupe key evita doppioni"
    assert second["duplicates"] == second["recipients"]

    repo = NotificationRepository(paths["NOTIFICATIONS_DB"])
    rows = repo.list_notifications(tenant_id="default", user_id=first_user_id(paths), limit=10)
    assert rows, "la notifica deve essere leggibile dal centro notifiche"
    assert rows[0].title == "Udienza audiovisiva registrata"
    assert rows[0].href == "/agenda/AG-1"
    assert rows[0].payload_json["remoteHearingUrl"] == remote_url
    assert rows[0].payload_json["remoteHearingVerified"] is True
    assert rows[0].payload_json["dueDateLabel"] == "01/07/2026"
    assert "Agenda e Scadenziario" in rows[0].body


def test_notifica_scadenza_automatica_deduplica_sul_presidio_stabile(tmp_path: Path) -> None:
    from flask import Flask

    from pct.auth import GestioneUtenti
    from pct.notifications import NotificationRepository, NotificationService
    from web.services.pec_pipeline_runtime import notify_auto_deadlines_for_paths

    paths = _paths(tmp_path)
    paths["AUTH_DB"] = str(tmp_path / "auth" / "utenti.json")
    paths["AUDIT_DB"] = str(tmp_path / "auth" / "audit.json")
    paths["NOTIFICATIONS_DB"] = str(tmp_path / "notifications" / "notifications.db")
    GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test-secret",
        bootstrap_admin_credentials_path=str(tmp_path / "auth" / "bootstrap_admin.json"),
    )
    user_id = first_user_id(paths)
    repo = NotificationRepository(paths["NOTIFICATIONS_DB"])
    NotificationService(repo).create_notification(
        tenant_id="default",
        user_id=user_id,
        type="pec_deadline",
        priority="important",
        title="Udienza audiovisiva registrata",
        body="Presidio PEC automatico: Collegamento audiovisivo da acquisire dal documento dell'udienza.",
        href="/agenda/OLD",
        source_type="pec_deadline",
        source_id="pec-msg-generico",
        dedupe_key="PEC_AUDIT:pec-msg-generico:deadline",
        payload_json={
            "deadlineId": "SCAD-STABILE",
            "remoteHearingAccessInfo": "Piattaforma: altra",
            "remoteHearingDetected": True,
            "remoteHearingPdfRequired": True,
        },
    )
    access_info = (
        "Istruzioni per acquisire il link udienza: depositare o comunicare una nota "
        "nel fascicolo telematico entro il 05/11/2026 con indirizzo e-mail per ricevere il link."
    )
    jobs = [
        {
            "job_type": "link",
            "message_id": message_id,
            "result": {
                "auto_deadline": {
                    "ok": True,
                    "deadline_id": "SCAD-STABILE",
                    "due_date": "2026-11-23",
                    "agenda": {"agenda_id": "AG-STABILE", "agenda_href": "/agenda/AG-STABILE"},
                    "remote_hearing": {
                        "remote_hearing_detected": True,
                        "remote_hearing_access_info": access_info,
                        "remote_hearing_pdf_required": True,
                    },
                }
            },
        }
        for message_id in ("pec-msg-generico", "pec-msg-arricchito")
    ]

    app = Flask(__name__)
    app.secret_key = "test-secret"
    with app.app_context():
        report = notify_auto_deadlines_for_paths(paths, tenant_label="default", jobs=jobs)

    rows = repo.list_notifications(tenant_id="default", user_id=user_id, limit=10)
    pec_rows = [row for row in rows if row.source_type == "pec_deadline"]
    assert report["created"] == 1
    assert report["duplicates"] == 1
    assert report["expired_legacy_duplicates"] >= 1
    assert len(pec_rows) == 1
    assert pec_rows[0].dedupe_key == "PEC_AUDIT:SCAD-STABILE:deadline"
    assert pec_rows[0].source_id == "SCAD-STABILE"
    assert pec_rows[0].payload_json["remoteHearingAccessInfo"] == access_info
    assert "Istruzioni per acquisire il link udienza" in pec_rows[0].body


def test_notifica_scadenza_automatica_usa_tenant_id_da_storage_manifest(tmp_path: Path) -> None:
    from flask import Flask
    import json

    from pct.auth import GestioneUtenti
    from pct.notifications import NotificationRepository
    from web.services.pec_pipeline_runtime import notify_auto_deadlines_for_paths

    paths = _paths(tmp_path)
    paths["AUTH_DB"] = str(tmp_path / "auth" / "utenti.json")
    paths["AUDIT_DB"] = str(tmp_path / "auth" / "audit.json")
    paths["NOTIFICATIONS_DB"] = str(tmp_path / "notifications" / "notifications.db")
    storage_config = tmp_path / "data" / "tenants" / "tenant-8bf98719c459" / "config" / "storage.json"
    storage_config.parent.mkdir(parents=True, exist_ok=True)
    storage_config.write_text(
        json.dumps({"slug": "studio-montagnese"}),
        encoding="utf-8",
    )
    (tmp_path / "data" / "tenants.json").write_text(
        json.dumps(
            {
                "studio-montagnese": {
                    "id": "tenant-local-studio-montagnese",
                    "slug": "studio-montagnese",
                    "storage_key": "tenant-8bf98719c459",
                }
            }
        ),
        encoding="utf-8",
    )
    paths["STORAGE_CONFIG"] = str(storage_config)
    GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test-secret",
        bootstrap_admin_credentials_path=str(tmp_path / "auth" / "bootstrap_admin.json"),
    )
    user_id = first_user_id(paths)
    jobs = [
        {
            "job_type": "link",
            "message_id": "pec-msg-storage-tenant",
            "result": {
                "auto_deadline": {
                    "ok": True,
                    "deadline_id": "SCAD-STORAGE",
                    "due_date": "2026-11-23",
                    "agenda": {"agenda_id": "AG-STORAGE", "agenda_href": "/agenda/AG-STORAGE"},
                    "remote_hearing": {
                        "remote_hearing_detected": True,
                        "remote_hearing_pdf_required": True,
                    },
                }
            },
        }
    ]

    app = Flask(__name__)
    app.secret_key = "test-secret"
    with app.app_context():
        report = notify_auto_deadlines_for_paths(paths, tenant_label="studio-montagnese", jobs=jobs)

    repo = NotificationRepository(paths["NOTIFICATIONS_DB"])
    tenant_rows = repo.list_notifications("tenant-local-studio-montagnese", user_id, limit=10)
    slug_rows = repo.list_notifications("studio-montagnese", user_id, limit=10)

    assert report["created"] == 1
    assert tenant_rows
    assert tenant_rows[0].source_id == "SCAD-STORAGE"
    assert slug_rows == []


def test_presidio_automatico_invia_una_sola_push_quando_il_link_diventa_verificato(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from flask import Flask

    from pct.auth import GestioneUtenti
    from pct.notifications import NotificationService
    from pct.notifications.service import PushDispatchSummary
    from web.services.pec_pipeline_runtime import notify_auto_deadlines_for_paths

    paths = _paths(tmp_path)
    paths["AUTH_DB"] = str(tmp_path / "auth" / "utenti.json")
    paths["AUDIT_DB"] = str(tmp_path / "auth" / "audit.json")
    paths["NOTIFICATIONS_DB"] = str(tmp_path / "notifications" / "notifications.db")
    GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test-secret",
        bootstrap_admin_credentials_path=str(tmp_path / "auth" / "bootstrap_admin.json"),
    )
    calls: list[dict[str, object]] = []

    def fake_dispatch(self, record):
        calls.append(dict(record.payload_json))
        return PushDispatchSummary(configured=True, attempted=1, sent=1)

    monkeypatch.setattr(NotificationService, "dispatch_web_push", fake_dispatch)
    base_deadline = {
        "ok": True,
        "deadline_id": "SCAD-PUSH-1",
        "due_date": "2026-10-29",
        "agenda": {"agenda_id": "AG-PUSH-1", "agenda_href": "/agenda/AG-PUSH-1"},
    }
    missing_jobs = [
        {
            "job_type": "link",
            "message_id": "pec-push-verificata",
            "result": {
                "auto_deadline": {
                    **base_deadline,
                    "remote_hearing": {
                        "remote_hearing_detected": True,
                        "remote_hearing_pdf_required": True,
                    },
                }
            },
        }
    ]
    link = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_push_verificata/0"
    verified_jobs = [
        {
            "job_type": "link",
            "message_id": "pec-push-verificata",
            "result": {
                "auto_deadline": {
                    **base_deadline,
                    "remote_hearing": {
                        "remote_hearing_detected": True,
                        "remote_hearing_url": link,
                        "remote_hearing_source": "decreto.pdf",
                        "remote_hearing_verified": True,
                    },
                }
            },
        }
    ]
    app = Flask(__name__)
    app.secret_key = "test-secret"
    with app.app_context():
        first = notify_auto_deadlines_for_paths(paths, tenant_label="default", jobs=missing_jobs)
        second = notify_auto_deadlines_for_paths(paths, tenant_label="default", jobs=verified_jobs)

    assert first["created"] >= 1
    assert second["duplicates"] >= 1
    assert len(calls) == 2
    assert calls[0]["remoteHearingPdfRequired"] is True
    assert calls[0]["remoteHearingUrl"] == ""
    assert calls[1]["remoteHearingUrl"] == link
    assert calls[1]["remoteHearingVerified"] is True


def test_presidio_automatico_notifica_ogni_udienza_della_stessa_pec(tmp_path: Path) -> None:
    from flask import Flask

    from pct.auth import GestioneUtenti
    from pct.notifications import NotificationRepository
    from web.services.pec_pipeline_runtime import notify_auto_deadlines_for_paths

    paths = _paths(tmp_path)
    paths["AUTH_DB"] = str(tmp_path / "auth" / "utenti.json")
    paths["AUDIT_DB"] = str(tmp_path / "auth" / "audit.json")
    paths["NOTIFICATIONS_DB"] = str(tmp_path / "notifications" / "notifications.db")
    GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test-secret",
        bootstrap_admin_credentials_path=str(tmp_path / "auth" / "bootstrap_admin.json"),
    )
    hearing_results = [
        {
            "ok": True,
            "deadline_id": f"SCAD-{index}",
            "due_date": f"2026-10-{28 + index:02d}",
            "agenda": {"agenda_id": f"AG-{index}"},
            "scheduled_message_id": f"pec-multi-push:hearing:{index}",
        }
        for index in (1, 2)
    ]
    jobs = [
        {
            "job_type": "link",
            "message_id": "pec-multi-push",
            "result": {"auto_deadline": {"ok": True, "hearing_results": hearing_results}},
        }
    ]
    app = Flask(__name__)
    app.secret_key = "test-secret"
    with app.app_context():
        report = notify_auto_deadlines_for_paths(paths, tenant_label="default", jobs=jobs)

    rows = NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications(
        tenant_id="default",
        user_id=first_user_id(paths),
        limit=10,
    )
    assert report["created"] == 2 * report["recipients"]
    assert {row.payload_json["deadlineId"] for row in rows} == {"SCAD-1", "SCAD-2"}


def first_user_id(paths: dict[str, str]) -> str:
    from pct.auth import GestioneUtenti

    gestore = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test-secret",
        crea_admin_se_vuoto=False,
    )
    return str(gestore.tutti(solo_attivi=True)[0].id)
