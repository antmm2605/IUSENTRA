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

    jobs = [
        {
            "job_type": "link",
            "message_id": "pec_msg_auto_1",
            "result": {
                "auto_deadline": {
                    "ok": True,
                    "deadline_id": "SCAD-1",
                    "due_date": "2026-07-01",
                    "agenda": {"agenda_id": "AG-1"},
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


def first_user_id(paths: dict[str, str]) -> str:
    from pct.auth import GestioneUtenti

    gestore = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test-secret",
        crea_admin_se_vuoto=False,
    )
    return str(gestore.tutti(solo_attivi=True)[0].id)
