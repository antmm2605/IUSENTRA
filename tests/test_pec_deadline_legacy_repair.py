from __future__ import annotations

import json

from pct.pec_pipeline import PecAuditRepository
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine


def test_repair_legacy_control_tower_promuove_sentenza_da_valutare(tmp_path):
    scadenziario_db = tmp_path / "scadenziario.json"
    pec_db = tmp_path / "pec_audit.sqlite"
    tenant_id = "studio-test"
    message_id = "pec_sentenza_monea"
    parsed_version_id = "pver_sentenza_monea"
    received_at = "2026-07-14T11:05:14Z"

    scadenziario = GestioneScadenziario(db_path=scadenziario_db)
    scadenza = scadenziario.nuova(
        "Verifica comunicazione di cancelleria e termini",
        TipoTermine.ADEMPIMENTO,
        "2026-07-15",
        id_fascicolo="2EE71A39",
        descrizione="Bozza da confermare generata da presidio PEC Control Tower.",
        note="Termine operativo non definitivo: conferma professionale obbligatoria.",
        source_event_type="provvedimento_da_esaminare",
        source_event_at="2026-07-14T11:05:14+00:00",
    )

    repo = PecAuditRepository(
        pec_db,
        tenant_id=tenant_id,
        scadenziario_db_path=scadenziario_db,
    )
    event_json = {
        "notifications": [
            {
                "notification_case": "judgment_to_notify",
                "source_file": "PEC",
                "reason": (
                    "Sentenza o provvedimento decisorio ricevuto: aprire presidio "
                    "per valutare o preparare la notifica."
                ),
            }
        ]
    }
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO pec_messages
            (id, tenant_id, account_email, folder, imap_uid, message_id_header, mime_sha256,
             mime_size, original_mime, received_at, ingested_at, linked_fascicolo_id, metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                message_id,
                tenant_id,
                "studio@example.pec.it",
                "INBOX",
                "1",
                "<sentenza-monea@example.test>",
                "sha-message",
                12,
                b"mime",
                received_at,
                received_at,
                "2EE71A39",
                json.dumps({"subject": "POSTA CERTIFICATA: COMUNICAZIONE 1394/2026/LAV"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO pec_parsed_versions
            (id, message_id, version, parser_version, parsed_json, parsed_sha256, created_at, created_by)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (parsed_version_id, message_id, 1, "test", "{}", "sha-parsed", received_at, "pytest"),
        )
        conn.execute(
            """
            INSERT INTO pec_attachments
            (id, message_id, parsed_version_id, attachment_index, filename, content_type,
             size_bytes, sha256, classification, classification_score, classification_reason, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "att_zip",
                message_id,
                parsed_version_id,
                1,
                "24262990s.pdf.zip",
                "application/zip",
                42,
                "sha-attachment",
                "sentenza",
                0.9,
                "sentenza a verbale",
                received_at,
            ),
        )
        conn.execute(
            """
            INSERT INTO pec_legal_events
            (id, tenant_id, message_id, parsed_version_id, rulepack_version, family,
             primary_event, priority, confidence, human_review_required, event_json, event_sha256, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "lev_sentenza",
                tenant_id,
                message_id,
                parsed_version_id,
                "test",
                "comunicazione_lavoro",
                "sentenza_a_verbale",
                "P1",
                0.86,
                1,
                json.dumps(event_json, ensure_ascii=False),
                "sha-event",
                received_at,
            ),
        )

    result = repo.repair_pec_deadlines(actor="pytest")

    assert result["ok"] is True
    assert result["checked"] == 1
    assert result["updated"] == 1

    refreshed = GestioneScadenziario(db_path=scadenziario_db).get(scadenza.id)
    assert refreshed is not None
    assert refreshed.titolo == "Sentenza da valutare per la notifica"
    assert refreshed.source_event_type == "sentenza_da_valutare_per_notifica"
    assert refreshed.id_fascicolo == "2EE71A39"
    assert f"PEC_AUDIT:{message_id}" in refreshed.note
    assert "Fonte documentale: 24262990s.pdf.zip" in refreshed.note


def test_repair_legacy_control_tower_non_abbina_due_pec_ravvicinate_senza_fascicolo(tmp_path):
    scadenziario_db = tmp_path / "scadenziario.json"
    pec_db = tmp_path / "pec_audit.sqlite"
    tenant_id = "studio-test"
    scadenziario = GestioneScadenziario(db_path=scadenziario_db)
    scadenza = scadenziario.nuova(
        "Verifica comunicazione di cancelleria e termini",
        TipoTermine.ADEMPIMENTO,
        "2026-07-15",
        id_fascicolo="",
        descrizione="Bozza da confermare generata da presidio PEC Control Tower.",
        note="Termine operativo non definitivo: conferma professionale obbligatoria.",
        source_event_type="provvedimento_da_esaminare",
        source_event_at="2026-07-14T11:05:30+00:00",
    )
    repo = PecAuditRepository(
        pec_db,
        tenant_id=tenant_id,
        scadenziario_db_path=scadenziario_db,
    )
    event_json = {
        "notifications": [
            {
                "notification_case": "judgment_to_notify",
                "reason": "Sentenza ricevuta: valutare la notifica.",
            }
        ]
    }
    with repo.connect() as conn:
        for index, received_at in enumerate(
            ("2026-07-14T11:05:14Z", "2026-07-14T11:06:00Z"),
            start=1,
        ):
            message_id = f"pec_sentenza_ravvicinata_{index}"
            parsed_version_id = f"pver_sentenza_ravvicinata_{index}"
            conn.execute(
                """
                INSERT INTO pec_messages
                (id, tenant_id, account_email, folder, imap_uid, message_id_header, mime_sha256,
                 mime_size, original_mime, received_at, ingested_at, linked_fascicolo_id, metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    message_id,
                    tenant_id,
                    "studio@example.pec.it",
                    "INBOX",
                    str(index),
                    f"<sentenza-ravvicinata-{index}@example.test>",
                    f"sha-message-{index}",
                    12,
                    b"mime",
                    received_at,
                    received_at,
                    f"FASCICOLO-{index}",
                    json.dumps({"subject": f"COMUNICAZIONE sentenza {index}"}),
                ),
            )
            conn.execute(
                """
                INSERT INTO pec_parsed_versions
                (id, message_id, version, parser_version, parsed_json, parsed_sha256, created_at, created_by)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    parsed_version_id,
                    message_id,
                    1,
                    "test",
                    "{}",
                    f"sha-parsed-{index}",
                    received_at,
                    "pytest",
                ),
            )
            conn.execute(
                """
                INSERT INTO pec_legal_events
                (id, tenant_id, message_id, parsed_version_id, rulepack_version, family,
                 primary_event, priority, confidence, human_review_required, event_json, event_sha256, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    f"lev_sentenza_ravvicinata_{index}",
                    tenant_id,
                    message_id,
                    parsed_version_id,
                    "test",
                    "comunicazione_lavoro",
                    "sentenza_a_verbale",
                    "P1",
                    0.86,
                    1,
                    json.dumps(event_json, ensure_ascii=False),
                    f"sha-event-{index}",
                    received_at,
                ),
            )

    assert repo._legacy_control_tower_sentence_candidate(scadenza) == {}
    result = repo.repair_pec_deadlines(actor="pytest")

    assert result["updated"] == 0
    refreshed = GestioneScadenziario(db_path=scadenziario_db).get(scadenza.id)
    assert refreshed is not None
    assert refreshed.titolo == "Verifica comunicazione di cancelleria e termini"
    assert "PEC_AUDIT:" not in refreshed.note


def test_repair_pec_presidio_sentenza_non_annulla_se_manca_termine_calcolabile(tmp_path):
    scadenziario_db = tmp_path / "scadenziario.json"
    pec_db = tmp_path / "pec_audit.sqlite"
    tenant_id = "studio-test"
    message_id = "pec_sentenza_romeo"
    parsed_version_id = "pver_sentenza_romeo"
    received_at = "2026-07-17T11:46:06Z"

    scadenziario = GestioneScadenziario(db_path=scadenziario_db)
    scadenza = scadenziario.nuova(
        "Valuta comunicazione di cancelleria PEC: POSTA CERTIFICATA: COMUNICAZIONE 1428/2026/LAV",
        TipoTermine.ADEMPIMENTO,
        "2026-07-21",
        id_fascicolo="78D6022C",
        descrizione="Presidio notifica creato da PEC.",
        note=(
            "IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:test:da_preparare\n"
            f"PEC_AUDIT:{message_id}\n"
            "Fonte documentale: 9732730s.pdf.zip"
        ),
        source_event_type="comunicazione_cancelleria",
        source_event_at=received_at,
    )

    repo = PecAuditRepository(
        pec_db,
        tenant_id=tenant_id,
        scadenziario_db_path=scadenziario_db,
    )
    event_json = {
        "notifications": [
            {
                "notification_case": "judgment_to_notify",
                "source_file": "9732730s.pdf.zip",
                "reason": "Sentenza a verbale ricevuta: valutare/preparare la notifica.",
            }
        ]
    }
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO pec_messages
            (id, tenant_id, account_email, folder, imap_uid, message_id_header, mime_sha256,
             mime_size, original_mime, received_at, ingested_at, linked_fascicolo_id, metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                message_id,
                tenant_id,
                "studio@example.pec.it",
                "INBOX",
                "2",
                "<sentenza-romeo@example.test>",
                "sha-message-romeo",
                12,
                b"mime",
                received_at,
                received_at,
                "78D6022C",
                json.dumps({"subject": "POSTA CERTIFICATA: COMUNICAZIONE 1428/2026/LAV"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO pec_parsed_versions
            (id, message_id, version, parser_version, parsed_json, parsed_sha256, created_at, created_by)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (parsed_version_id, message_id, 1, "test", "{}", "sha-parsed", received_at, "pytest"),
        )
        conn.execute(
            """
            INSERT INTO pec_attachments
            (id, message_id, parsed_version_id, attachment_index, filename, content_type,
             size_bytes, sha256, classification, classification_score, classification_reason, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "att_zip_romeo",
                message_id,
                parsed_version_id,
                1,
                "9732730s.pdf.zip",
                "application/zip",
                42,
                "sha-attachment-romeo",
                "sentenza",
                0.9,
                "sentenza a verbale",
                received_at,
            ),
        )
        conn.execute(
            """
            INSERT INTO pec_legal_events
            (id, tenant_id, message_id, parsed_version_id, rulepack_version, family,
             primary_event, priority, confidence, human_review_required, event_json, event_sha256, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "lev_sentenza_romeo",
                tenant_id,
                message_id,
                parsed_version_id,
                "test",
                "comunicazione_lavoro",
                "sentenza_a_verbale",
                "P1",
                0.86,
                1,
                json.dumps(event_json, ensure_ascii=False),
                "sha-event-romeo",
                received_at,
            ),
        )

    result = repo.repair_pec_deadlines(actor="pytest")

    assert result["ok"] is True
    assert result["checked"] == 1
    assert result["updated"] == 1

    refreshed = GestioneScadenziario(db_path=scadenziario_db).get(scadenza.id)
    assert refreshed is not None
    assert refreshed.stato == StatoTermine.APERTO
    assert refreshed.titolo == "Sentenza da valutare per la notifica"
    assert refreshed.source_event_type == "sentenza_da_valutare_per_notifica"
    assert "IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:test:da_preparare" in refreshed.note
    assert f"PEC_AUDIT:{message_id}" in refreshed.note
    assert "Attività per l'avvocato: esaminare la sentenza" in refreshed.note
