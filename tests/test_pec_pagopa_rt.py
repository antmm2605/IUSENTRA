"""Intercettazione automatica delle Ricevute Telematiche pagoPA da PEC/email.

La pipeline del presidio riconosce gli allegati RT.xml (schema ministeriale
PagamentiTelematiciGiustizia), li verifica e li archivia nel fascicolo
collegato — o agganciato per RG dalla causale, solo con match univoco.
Percorso conforme alle regole PST: nessun download autonomo dal portale.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.pec_pipeline import AttachmentPayload, PecAuditRepository

_NS = "http://www.digitpa.gov.it/schemas/2011/Pagamenti/"


def _rt_xml(importo: str = "237.00", iuv: str = "IUV-TEST-1", causale: str = "Contributo unificato RG 1234/2024") -> bytes:
    return (
        f'<pay_i:RT xmlns:pay_i="{_NS}">'
        "<pay_i:dataOraMessaggioRicevuta>2026-08-12T09:30:00</pay_i:dataOraMessaggioRicevuta>"
        "<pay_i:datiPagamento>"
        "<pay_i:codiceEsitoPagamento>0</pay_i:codiceEsitoPagamento>"
        f"<pay_i:importoTotalePagato>{importo}</pay_i:importoTotalePagato>"
        f"<pay_i:identificativoUnivocoVersamento>{iuv}</pay_i:identificativoUnivocoVersamento>"
        "<pay_i:datiSingoloPagamento>"
        f"<pay_i:singoloImportoPagato>{importo}</pay_i:singoloImportoPagato>"
        "<pay_i:dataEsitoSingoloPagamento>2026-08-12</pay_i:dataEsitoSingoloPagamento>"
        "<pay_i:identificativoUnivocoRiscossione>IUR-1</pay_i:identificativoUnivocoRiscossione>"
        f"<pay_i:causaleVersamento>{causale}</pay_i:causaleVersamento>"
        "</pay_i:datiSingoloPagamento>"
        "</pay_i:datiPagamento>"
        "</pay_i:RT>"
    ).encode("utf-8")


def _payload(filename: str, data: bytes, index: int = 0) -> AttachmentPayload:
    return AttachmentPayload(index=index, filename=filename, content_type="application/xml", data=data)


@pytest.fixture
def ambiente(tmp_path):
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )
    fascicolo = fascicoli.nuovo(
        titolo="Rossi c/ Bianchi",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Rossi Mario",
        numero_rg="1234",
        anno_rg=2024,
    )
    repo = PecAuditRepository(
        db_path=str(tmp_path / "pec_audit.sqlite"),
        fascicoli_db_path=str(tmp_path / "fascicoli.json"),
        fascicoli_docs_path=str(tmp_path / "documenti"),
    )
    return SimpleNamespace(repo=repo, fascicoli=fascicoli, fascicolo=fascicolo, tmp_path=tmp_path)


def _prepara(monkeypatch, ambiente, payloads, link):
    monkeypatch.setattr(
        ambiente.repo, "_attachment_payloads_for_message", lambda conn, message_id: ({}, payloads)
    )
    monkeypatch.setattr(ambiente.repo, "latest_link", lambda conn, message_id: link)


def test_rt_archiviata_nel_fascicolo_collegato(monkeypatch, ambiente):
    _prepara(monkeypatch, ambiente, [_payload("RT_contributo.xml", _rt_xml())], {"fascicolo_id": ambiente.fascicolo.id})
    esito = ambiente.repo.reconcile_pagopa_payment_receipt("MSG-1")
    assert esito["ok"] is True and esito["skipped"] is False
    assert len(esito["archiviate"]) == 1
    archiviata = esito["archiviate"][0]
    assert archiviata["ok"] is True
    assert archiviata["pagamento_eseguito"] is True
    assert archiviata["importo"] == 237.00
    # Rilettura con manager fresco: il repo scrive su una propria istanza.
    riletto = GestioneFascicoli(
        db_path=str(ambiente.tmp_path / "fascicoli.json"),
        documents_dir=str(ambiente.tmp_path / "documenti"),
        archive_dir=str(ambiente.tmp_path / "archivio"),
    )
    documenti = riletto.get(ambiente.fascicolo.id).documenti
    assert any("IUSENTRA_PAGOPA_RT" in str(d.note or "") for d in documenti)


def test_idempotente_per_hash(monkeypatch, ambiente):
    _prepara(monkeypatch, ambiente, [_payload("RT.xml", _rt_xml())], {"fascicolo_id": ambiente.fascicolo.id})
    primo = ambiente.repo.reconcile_pagopa_payment_receipt("MSG-1")
    secondo = ambiente.repo.reconcile_pagopa_payment_receipt("MSG-1")
    assert len(primo["archiviate"]) == 1
    assert secondo["archiviate"] == []
    assert secondo["gia_presenti"] == 1


def test_match_per_rg_dalla_causale_senza_link(monkeypatch, ambiente):
    _prepara(monkeypatch, ambiente, [_payload("RT.xml", _rt_xml(causale="Pagamento CU R.G. 1234/2024 Tribunale di Milano"))], {})
    esito = ambiente.repo.reconcile_pagopa_payment_receipt("MSG-2")
    assert esito["skipped"] is False
    assert esito["fascicolo_id"] == ambiente.fascicolo.id


def test_match_ambiguo_non_aggancia(monkeypatch, ambiente):
    # Secondo fascicolo con lo stesso RG: match non univoco → nessun automatismo.
    ambiente.fascicoli.nuovo(
        titolo="Altro giudizio", tipo=TipoFascicolo.CIVILE, nome_cliente="Verdi", numero_rg="1234", anno_rg=2024
    )
    _prepara(monkeypatch, ambiente, [_payload("RT.xml", _rt_xml())], {})
    esito = ambiente.repo.reconcile_pagopa_payment_receipt("MSG-3")
    assert esito["skipped"] is True
    assert esito["reason"] == "fascicolo_non_determinabile"


def test_ricevuta_prima_dell_iscrizione_a_ruolo_agganciata_per_iuv(monkeypatch, ambiente):
    # Causale senza RG (pagamento prima dell'iscrizione): vale lo IUV dell'avviso generato nel fascicolo.
    altro = ambiente.fascicoli.nuovo(titolo="Nuova causa", tipo=TipoFascicolo.CIVILE, nome_cliente="Verdi")
    ambiente.fascicoli.aggiorna(altro.id, pagamenti={"pagopa_portale": {"avvisi": [{"numero_avviso": "301000000000012345"}]}})
    causale = "Contributo unificato - Verdi c. Neri - Tribunale di Roma"
    _prepara(monkeypatch, ambiente, [_payload("RT.xml", _rt_xml(iuv="01000000000012345", causale=causale))], {})
    esito = ambiente.repo.reconcile_pagopa_payment_receipt("MSG-5")
    assert esito["skipped"] is False and esito["fascicolo_id"] == altro.id
    # Stesso IUV in due fascicoli: nessun aggancio automatico.
    terzo = ambiente.fascicoli.nuovo(titolo="Copia", tipo=TipoFascicolo.CIVILE, nome_cliente="Verdi")
    ambiente.fascicoli.aggiorna(terzo.id, pagamenti={"pagopa_portale": {"avvisi": [{"iuv": "01000000000012345"}]}})
    _prepara(monkeypatch, ambiente, [_payload("RT2.xml", _rt_xml(iuv="01000000000012345", causale=causale, importo="98.00"))], {})
    assert ambiente.repo.reconcile_pagopa_payment_receipt("MSG-6")["reason"] == "fascicolo_non_determinabile"


def test_fascicolo_dell_avviso_senza_iuv_o_con_errore():
    from pct.pagamenti_giustizia_registro import fascicolo_dell_avviso

    assert fascicolo_dell_avviso([], "") == ""

    class Guasto:
        def tutti(self):
            raise RuntimeError("archivio")

    from pct.pec_pipeline import PecAuditRepository as Repo

    assert Repo._pagopa_match_fascicolo_da_iuv(object.__new__(Repo), Guasto(), ["1"]) == ""


def test_allegato_non_rt_ignorato(monkeypatch, ambiente):
    payloads = [
        _payload("fattura.xml", b"<fattura><importo>10</importo></fattura>"),
        _payload("atto.pdf", b"%PDF-1.4 finto"),
    ]
    _prepara(monkeypatch, ambiente, payloads, {"fascicolo_id": ambiente.fascicolo.id})
    esito = ambiente.repo.reconcile_pagopa_payment_receipt("MSG-4")
    assert esito["skipped"] is True
    assert esito["reason"] == "nessuna_rt_pagopa"
