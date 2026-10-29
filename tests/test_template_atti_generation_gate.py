from __future__ import annotations

from pct.studio_timbro import StudioTimbro
from pct.template_atti_lex_service import create_editor_draft
from pct.template_normative_compliance import analyze_template_compliance


def _stamp():
    return StudioTimbro.from_payload({"studio_nome": "Studio Test", "professionista_nome": "Avv. Test"}).to_payload()


def _cit_payload():
    return {
        "case_id": "fas-1",
        "id_cliente": "cli-1",
        "client_or_sender": "Mario Rossi",
        "counterparty_or_recipient": "Bianchi",
        "court_name": "Tribunale di Roma",
        "plaintiff": "Mario Rossi",
        "defendant": "Bianchi",
        "lawyer_tax_code": "TSTTST70A01H501A",
        "lawyer_pec": "avv@test.pec",
        "claim_subject": "Domanda",
        "facts": "Fatti.",
        "legal_arguments": "Diritto.",
        "evidence_means": "Documenti.",
        "documents_offered": "Contratto",
        "hearing_date": "2026-10-20",
        "appearance_notice": "Invito.",
        "ritual_warnings": "Avvertimenti.",
        "case_value": "10000",
        "requests_or_conclusions": "Conclusioni.",
        "attachments_list": "Contratto",
        "_studio_timbro": _stamp(),
    }


def test_gate_ok_restituisce_editor_url_e_scrive_editor():
    written = {}

    def writer(**kwargs):
        written.update(kwargs)
        return {
            "ok": True,
            "document_id": "doc-1",
            "editor_url": "/fascicoli/fas-1/documenti/doc-1/editor",
            "filename": "atto.html",
        }

    compliance = analyze_template_compliance("CIV_CIT_001", _cit_payload())
    result = create_editor_draft(
        "CIV_CIT_001",
        _cit_payload(),
        "fas-1",
        "utente-1",
        rendered_text="Atto di citazione",
        document_writer=writer,
        compliance_result=compliance,
        # Fonti del registro senza impronta (audit 29/10/2026): solo bozza di lavoro confermata.
        requested_draft="working_draft",
        confirmed_warning=True,
    )

    assert result.ok is True
    assert result.editor_url.endswith("/editor")
    assert result.to_dict()["editor_url"] == result.editor_url
    assert written["model_code"] == "CIV_CIT_001"


def test_bozza_archiviata_come_docx_reale_con_stili():
    from io import BytesIO
    from types import SimpleNamespace
    from zipfile import ZipFile

    written = {}

    class Repository:
        def aggiungi_documento(self, case_id, filename, kind, content, **metadata):
            written.update(filename=filename, content=content, metadata=metadata)
            return SimpleNamespace(id="doc-word")

    payload = _cit_payload()
    result = create_editor_draft(
        "CIV_CIT_001", payload, "fas-1", "utente-1",
        rendered_text="Atto di citazione",
        fascicoli_repo=Repository(), encrypt_func=lambda value: value,
        editor_html_builder=lambda _: (
            '<style>@page{margin:20mm}</style>'
            '<p style="text-align:center"><strong>Atto di citazione</strong></p>'
        ),
        compliance_result=analyze_template_compliance("CIV_CIT_001", payload),
        requested_draft="working_draft",
        confirmed_warning=True,
    )

    assert result.ok, result.errors
    assert written["filename"].endswith(".docx")
    with ZipFile(BytesIO(written["content"])) as archive:
        body = archive.read("word/document.xml").decode("utf-8")
        assert "Atto di citazione" in body
        assert "@page" not in body
        assert 'w:val="center"' in body
        assert "<w:b" in body
        assert b"doNotExpandShiftReturn" in archive.read("word/settings.xml")
    assert written["metadata"]["fonte_documento"] == "TEMPLATE_ATTI_COMPILATORE"


def test_word_conserva_richiesta_esplicita_di_espansione_ultima_riga():
    from io import BytesIO
    from zipfile import ZipFile
    from pct.editor import html_to_docx

    content = html_to_docx('<p style="text-align:justify;text-align-last:justify">Prima<br>Seconda</p>')
    with ZipFile(BytesIO(content)) as archive:
        assert b"doNotExpandShiftReturn" not in archive.read("word/settings.xml")


def test_gate_block_impedisce_creazione_bozza_finale():
    written = {}

    def writer(**kwargs):
        written.update(kwargs)
        return {"ok": True, "document_id": "doc-block"}

    payload = {
        "case_id": "fas-1",
        "competent_court": "Tribunale di Roma",
        "claimant": "Mario Rossi",
        "debtor": "Bianchi",
        "credit_source": "Fattura",
        "requested_amount": "1000",
        "credit_due_date": "2026-05-01",
        "_studio_timbro": _stamp(),
    }
    compliance = analyze_template_compliance("CIV_RDI_001", payload)
    result = create_editor_draft(
        "CIV_RDI_001",
        payload,
        "fas-1",
        "utente-1",
        rendered_text="Ricorso monitorio",
        document_writer=writer,
        compliance_result=compliance,
        requested_draft="final_draft",
    )

    assert result.ok is False
    assert result.created_as == "blocked"
    assert result.editor_url == ""
    assert written == {}


def test_gate_non_disponibile_non_bypassa_il_writer():
    written = {}

    def writer(**kwargs):
        written.update(kwargs)
        return {"ok": True, "document_id": "doc-bypass"}

    result = create_editor_draft(
        "CIV_CIT_001",
        _cit_payload(),
        "fas-1",
        "utente-1",
        rendered_text="Atto",
        document_writer=writer,
        compliance_result=object(),
        requested_draft="final_draft",
    )

    assert result.ok is False
    assert result.created_as == "blocked"
    assert result.editor_url == ""
    assert written == {}


def test_gate_warning_crea_solo_bozza_lavoro_con_conferma():
    payload = _cit_payload()
    payload.update(
        {
            "proceeding_number": "123/2026",
            "defendant": "Bianchi",
            "plaintiff": "Mario Rossi",
            "position_on_facts": "Difese sui fatti.",
            "procedural_exceptions": "Nessuna.",
            "merit_exceptions": "Eccezioni.",
            "evidence_means": "Documenti.",
            "documents_offered": "Atto notificato",
        }
    )
    compliance = analyze_template_compliance("CIV_COM_001", payload)
    first = create_editor_draft(
        "CIV_COM_001",
        payload,
        "fas-1",
        "utente-1",
        rendered_text="Comparsa",
        document_writer=lambda **kwargs: {"ok": True, "document_id": "no"},
        compliance_result=compliance,
        requested_draft="final_draft",
    )
    assert first.ok is False
    assert first.requires_confirmation is True

    written = {}

    def writer(**kwargs):
        written.update(kwargs)
        return {"ok": True, "document_id": "doc-warn", "open_url": "/fascicoli/fas-1/documenti/doc-warn/editor"}

    second = create_editor_draft(
        "CIV_COM_001",
        payload,
        "fas-1",
        "utente-1",
        rendered_text="Comparsa",
        document_writer=writer,
        compliance_result=compliance,
        requested_draft="working_draft",
        confirmed_warning=True,
    )
    assert second.ok is True
    assert second.created_as == "working_draft"
    assert written["rendered_text"].startswith("DA REVISIONARE")
