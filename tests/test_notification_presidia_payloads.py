from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from web.services import notification_presidia_payloads as payloads


def test_payload_pratica_usa_cliente_oggetto_rg_e_ufficio_del_tenant(monkeypatch) -> None:
    fascicolo = SimpleNamespace(
        nome_cliente="Giuseppe Alfano",
        titolo="Carta docente - MIM",
        oggetto="",
        rg_completo="RG 1100/2026",
        numero_rg="1100",
        anno_rg="2026",
        tribunale="Tribunale di Padova",
    )
    repository = SimpleNamespace(get=lambda identifier: fascicolo if identifier == "C3565650" else None)
    import web.helpers

    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: repository)

    practice = payloads._practice_payload("C3565650")

    assert practice == {
        "id": "C3565650",
        "label": "Giuseppe Alfano",
        "client": "Giuseppe Alfano",
        "subject": "Carta docente - MIM",
        "rg": "1100/2026",
        "office": "Tribunale di Padova",
        "href": "/fascicoli/C3565650",
    }


def test_payload_non_espone_chiavi_tecniche_in_caso_o_fonti() -> None:
    row = {
        "notification_case": "judgment_to_notify_review",
        "legal_basis_json": json.dumps(
            [
                {"id": "src.it.l53_1994.art3bis"},
                {"id": "src.it.cpc.art429"},
            ]
        ),
    }

    assert payloads._notification_case_label(row["notification_case"]) == "Sentenza da valutare per la notifica"
    assert payloads._legal_sources(row) == [
        "Legge 21 gennaio 1994, n. 53, art. 3-bis",
        "Codice di procedura civile, art. 429",
    ]


def test_payload_pratica_non_espone_l_identificativo_interno_se_il_fascicolo_non_e_risolto(monkeypatch) -> None:
    repository = SimpleNamespace(get=lambda _identifier: None)
    import web.helpers

    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: repository)

    practice = payloads._practice_payload("FB586324")

    assert practice["id"] == "FB586324"
    assert practice["label"] == "Pratica da completare"
    assert practice["client"] == ""
    assert practice["subject"] == ""
    assert practice["href"] == "/fascicoli/FB586324"


def test_payload_cursor_accetta_formato_pubblico_del_repository() -> None:
    encoded = payloads._cursor_encode({"updatedAt": "2026-07-21T22:50:00+02:00", "id": "presidio-1"})

    assert encoded
    assert payloads._cursor_decode(encoded) == ("2026-07-21T22:50:00+02:00", "presidio-1")


def test_payload_notifica_necessaria_confermata_non_sembra_gia_eseguita(monkeypatch) -> None:
    repository = SimpleNamespace(get=lambda _identifier: None)
    import web.helpers

    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: repository)

    item = payloads._summary(
        {
            "id": "presidio-1",
            "fascicoloId": "C3565650",
            "status": "NOTIFICATION_CONFIRMED",
            "notificationCase": "judgment_to_notify_review",
        },
        {
            "id": "presidio-1",
            "fascicolo_id": "C3565650",
            "status": "NOTIFICATION_CONFIRMED",
            "notification_case": "judgment_to_notify_review",
            "channel": "pec",
            "priority": "P1",
            "confidence": 0.86,
            "detection_reason": "Sentenza da valutare per la notifica.",
        },
        [],
        [],
        [],
    )

    assert item["status_label"] == "Notifica necessaria confermata"
    assert item["next_action"] == "Verifica destinatari e prepara relata"


def test_payload_offre_modifica_decisione_solo_dopo_conferma_pre_invio() -> None:
    permissions = {
        "can_write": True,
        "can_link_document": True,
    }

    confirmed_actions = payloads._available_actions(
        {"status": "NOTIFICATION_CONFIRMED", "fascicolo_id": "FASC-1"},
        permissions,
        False,
    )
    revision = next(action for action in confirmed_actions if action["id"] == "revise-decision")
    confirm = next(action for action in confirmed_actions if action["id"] == "confirm")

    assert revision == {
        "id": "revise-decision",
        "label": "Modifica decisione",
        "kind": "mutation",
        "mutation": "revise-decision",
        "enabled": True,
        "disabled_reason": "",
        "tone": "neutral",
    }
    assert confirm["enabled"] is False
    assert confirm["disabled_reason"] == "Decisione già registrata. Puoi modificarla qui sotto."

    for status in ("READY_TO_SEND", "SENT_WAITING_RAC", "PROOF_DEPOSITED", "CLOSED"):
        actions = payloads._available_actions(
            {"status": status, "fascicolo_id": "FASC-1"},
            permissions,
            False,
        )
        assert all(action["id"] != "revise-decision" for action in actions)


def test_documento_da_pec_usa_il_lettore_tenant_aware_e_non_e_originale() -> None:
    document = payloads._public_document(
        {
            "id": "notification-row-1",
            "fascicolo_document_id": "",
            "document_role": "office_pec_copy",
            "document_version": "1",
            "original_filename": "9732730s.pdf.zip",
            "authoritative": 1,
        },
        fascicolo_id="78D6022C",
        source_message_id="pec_d23c133a4ef8ada88ecb8c08",
        practice={
            "client": "Romeo Maria",
            "subject": "Romeo Maria c. MIM",
            "rg": "1428/2026",
            "office": "TRIBUNALE DI PALMI",
        },
        portal_context={
            "ufficio": "Tribunale di Palmi",
            "ufficio_codice": "0800570094",
            "numero": "1428",
            "anno": "2026",
            "schema": "lavoro",
            "materia": "Lavoro e previdenza",
            "registro": "LAV",
            "tabella_ministeriale": "SICID_LAVORO",
            "servizio_pst_preferito": "JPW_SIL_DISTR",
            "registro_portale": "LAV",
            "tipo_documento": "sentenza",
        },
    )

    assert document["id"] == "notification-row-1"
    assert document["role_label"] == "PEC di cancelleria · copia informativa"
    assert document["authoritative"] is False
    assert document["original_acquisition_required"] is True
    assert document["viewer_url"] == (
        "/api/v1/ui/email/source/pec_d23c133a4ef8ada88ecb8c08?name=9732730s.pdf.zip"
    )
    assert document["download_url"] == (
        "/api/v1/ui/email/source/pec_d23c133a4ef8ada88ecb8c08?name=9732730s.pdf.zip&download=1"
    )
    assert document["original_acquisition_url"].startswith(
        "/portali/pst/acquisizione?id_fasc=78D6022C&fascicolo_id=78D6022C"
    )
    assert "pec_id=pec_d23c133a4ef8ada88ecb8c08" in document["original_acquisition_url"]
    acquisition_query = parse_qs(urlparse(document["original_acquisition_url"]).query)
    assert acquisition_query["numero"] == ["1428"]
    assert acquisition_query["anno"] == ["2026"]
    assert acquisition_query["ufficio"] == ["Tribunale di Palmi"]
    assert acquisition_query["ufficio_codice"] == ["0800570094"]
    assert acquisition_query["assistito"] == ["Romeo Maria"]
    assert acquisition_query["oggetto"] == ["Romeo Maria c. MIM"]
    assert acquisition_query["schema"] == ["lavoro"]
    assert acquisition_query["materia"] == ["Lavoro e previdenza"]
    assert acquisition_query["registro"] == ["LAV"]
    assert acquisition_query["tabella_ministeriale"] == ["SICID_LAVORO"]
    assert acquisition_query["servizio_pst_preferito"] == ["JPW_SIL_DISTR"]
    assert acquisition_query["tipo_documento"] == ["sentenza"]


def test_contesto_pst_deriva_registro_e_codice_ufficio_dalla_pec_indicizzata() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE pec_messages (id TEXT, tenant_id TEXT);
        CREATE TABLE pec_parsed_versions (
            message_id TEXT,
            version INTEGER,
            parsed_json TEXT
        );
        """
    )
    parsed = {
        "fields": {
            "cliente": {"value": "ROMEO MARIA"},
            "codice_ufficio": {"value": "0800570094"},
            "ufficio_giudiziario": {"value": "Tribunale di Palmi"},
            "evento_processuale": {"value": "SENTENZA A VERBALE (art. 127-ter c.p.c.)"},
        },
        "legal_workflow": {
            "registri": [{
                "anno": "2026",
                "materia": "lavoro",
                "numero": "1428",
                "registro_normalizzato": "LAV",
                "tabella_ministeriale": "SICID_LAVORO",
            }]
        },
    }
    connection.execute(
        "INSERT INTO pec_messages VALUES (?, ?)",
        ("pec-source", "tenant-1"),
    )
    connection.execute(
        "INSERT INTO pec_parsed_versions VALUES (?, ?, ?)",
        ("pec-source", 1, json.dumps(parsed)),
    )
    connection.commit()

    class Repo:
        tenant_id = "tenant-1"

        def connection(self):
            return connection

    assert payloads._pec_portal_acquisition_context(
        Repo(),
        "pec-source",
        expected_rg="1428/2026",
    ) == {
        "ufficio": "Tribunale di Palmi",
        "ufficio_codice": "0800570094",
        "numero": "1428",
        "anno": "2026",
        "assistito": "ROMEO MARIA",
        "schema": "lavoro",
        "materia": "Lavoro e previdenza",
        "registro": "LAV",
        "tabella_ministeriale": "SICID_LAVORO",
        "servizio_pst_preferito": "JPW_SIL_DISTR",
        "registro_portale": "LAV",
        "tipo_documento": "sentenza",
    }


def test_originale_pst_collegato_usa_le_route_reali_del_fascicolo() -> None:
    document = payloads._public_document(
        {
            "id": "notification-row-2",
            "fascicolo_document_id": "DOC/42",
            "document_role": "portal_original",
            "original_filename": "Sentenza.pdf",
            "authoritative": 1,
        },
        fascicolo_id="FASC/1",
        source_message_id="pec-source",
        has_portal_original=True,
    )

    assert document["role_label"] == "Originale acquisito dal Portale Servizi"
    assert document["authoritative"] is True
    assert document["original_acquisition_required"] is False
    assert document["original_acquisition_url"] == ""
    assert document["viewer_url"] == "/fascicoli/FASC%2F1/documenti/DOC%2F42/visualizza"
    assert document["download_url"] == "/fascicoli/FASC%2F1/documenti/DOC%2F42/scarica"


def test_documenti_collegabili_espongono_nomi_leggibili_non_soli_id(monkeypatch) -> None:
    fascicolo = SimpleNamespace(
        documenti=[
            SimpleNamespace(
                id="doc-interno-1",
                nome="Sentenza.pdf",
                nome_originale="Sentenza_originale.pdf",
                tipo=SimpleNamespace(value="SENTENZA"),
            )
        ]
    )
    repository = SimpleNamespace(get=lambda identifier: fascicolo if identifier == "FASC-1" else None)
    import web.helpers

    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: repository)

    assert payloads._linkable_documents("FASC-1") == [
        {
            "value": "doc-interno-1",
            "label": "Sentenza.pdf",
            "document_name": "Sentenza.pdf",
        }
    ]
