"""Ricevute telematiche pagoPA di giustizia (RT.xml) e riconciliazione in busta.

Fonte certa: schema ministeriale ``PagamentiTelematiciGiustizia`` (XSD 6.x,
namespace digitpa Pagamenti) e vademecum pagamenti PST. La RT e' la prova
tecnica del pagamento nei depositi: esito 0 = eseguito; esiti 1-4 non provano.
"""

from __future__ import annotations

from pct.busta import Allegato, BustaTelematica, DatiBusta
from pct.pagamenti_giustizia import (
    e_ricevuta_telematica,
    parse_rt,
    riepilogo_rt_allegate,
    verifica_rt_per_deposito,
)

_NS = "http://www.digitpa.gov.it/schemas/2011/Pagamenti/"


def _rt_xml(esito: str = "0", importo: str = "237.00", iuv: str = "RF123456789012345678") -> bytes:
    return (
        f'<pay_i:RT xmlns:pay_i="{_NS}">'
        "<pay_i:versioneOggetto>6.2</pay_i:versioneOggetto>"
        "<pay_i:dataOraMessaggioRicevuta>2026-08-10T09:30:00</pay_i:dataOraMessaggioRicevuta>"
        "<pay_i:enteBeneficiario>"
        "<pay_i:denominazioneBeneficiario>Ministero della Giustizia</pay_i:denominazioneBeneficiario>"
        "</pay_i:enteBeneficiario>"
        "<pay_i:soggettoPagatore>"
        "<pay_i:anagraficaPagatore>Rossi Mario</pay_i:anagraficaPagatore>"
        "</pay_i:soggettoPagatore>"
        "<pay_i:datiPagamento>"
        f"<pay_i:codiceEsitoPagamento>{esito}</pay_i:codiceEsitoPagamento>"
        f"<pay_i:importoTotalePagato>{importo}</pay_i:importoTotalePagato>"
        f"<pay_i:identificativoUnivocoVersamento>{iuv}</pay_i:identificativoUnivocoVersamento>"
        "<pay_i:CodiceContestoPagamento>CCP-1</pay_i:CodiceContestoPagamento>"
        "<pay_i:datiSingoloPagamento>"
        f"<pay_i:singoloImportoPagato>{importo}</pay_i:singoloImportoPagato>"
        "<pay_i:dataEsitoSingoloPagamento>2026-08-10</pay_i:dataEsitoSingoloPagamento>"
        "<pay_i:identificativoUnivocoRiscossione>IUR-77</pay_i:identificativoUnivocoRiscossione>"
        "<pay_i:causaleVersamento>Contributo unificato RG 1234/2024</pay_i:causaleVersamento>"
        "</pay_i:datiSingoloPagamento>"
        "</pay_i:datiPagamento>"
        "</pay_i:RT>"
    ).encode("utf-8")


# --- Parse ------------------------------------------------------------------------


def test_parse_rt_eseguita_estrae_campi_ministeriali():
    rt = parse_rt(_rt_xml())
    assert rt is not None
    assert rt.pagamento_eseguito is True
    assert rt.esito_label == "Pagamento eseguito"
    assert rt.importo_totale == 237.00
    assert rt.iuv == "RF123456789012345678"
    assert rt.codice_contesto_pagamento == "CCP-1"
    assert rt.ente_beneficiario == "Ministero della Giustizia"
    assert rt.pagatore == "Rossi Mario"
    assert rt.iur == ["IUR-77"]
    assert "Contributo unificato" in rt.causale


def test_parse_rt_non_eseguita():
    rt = parse_rt(_rt_xml(esito="1", importo="0.00"))
    assert rt is not None
    assert rt.pagamento_eseguito is False
    assert rt.esito_label == "Pagamento non eseguito"


def test_xml_generico_non_e_rt():
    generico = b"<fattura><importo>10.00</importo></fattura>"
    assert e_ricevuta_telematica(generico) is False
    assert parse_rt(generico) is None
    assert parse_rt(b"non-xml") is None


def test_e_ricevuta_telematica_riconosce_rt():
    assert e_ricevuta_telematica(_rt_xml()) is True


def test_rt_con_entita_interna_viene_rifiutata_senza_espansione():
    xml_ostile = b"""<?xml version="1.0"?>
<!DOCTYPE RT [<!ENTITY dato "contenuto espanso">]>
<RT><causaleVersamento>&dato;</causaleVersamento></RT>"""
    assert e_ricevuta_telematica(xml_ostile) is False
    assert parse_rt(xml_ostile) is None


def test_rt_con_entita_esterna_viene_rifiutata_senza_accesso_alla_risorsa():
    xml_ostile = b"""<?xml version="1.0"?>
<!DOCTYPE RT [<!ENTITY dato SYSTEM "file:///etc/passwd">]>
<RT><causaleVersamento>&dato;</causaleVersamento></RT>"""
    assert e_ricevuta_telematica(xml_ostile) is False
    assert parse_rt(xml_ostile) is None


# --- Verifica per deposito --------------------------------------------------------


def test_esito_negativo_avvisa_senza_bloccare():
    # Scelta di prodotto: la decisione sull'invio resta all'avvocato, che
    # conferma e procede — l'esito negativo produce un avviso, mai un blocco.
    rt = parse_rt(_rt_xml(esito="1", importo="0.00"))
    issues = verifica_rt_per_deposito(rt, importo_atteso=237.0)
    assert any(i["code"] == "RT-ESITO-NEGATIVO" and i["level"] == "WARN" for i in issues)
    assert not any(i["level"] == "BLOCK" for i in issues)


def test_deposito_esente_rt_negativa_segnala_allegato_errato():
    # Esenzione (es. autocertificazione reddituale art. 9 c.1-bis D.P.R.
    # 115/2002 nei giudizi di lavoro): il pagamento non e' dovuto, una RT
    # negativa allegata e' quasi certamente un file sbagliato.
    rt = parse_rt(_rt_xml(esito="1", importo="0.00"))
    issues = verifica_rt_per_deposito(rt, pagamento_richiesto=False)
    assert [i["code"] for i in issues] == ["RT-NON-NECESSARIA"]
    assert issues[0]["level"] == "WARN"


def test_importo_difforme_avvisa_ma_non_blocca():
    rt = parse_rt(_rt_xml(importo="98.00"))
    issues = verifica_rt_per_deposito(rt, importo_atteso=237.0)
    assert [i["code"] for i in issues] == ["RT-IMPORTO-DIFFORME"]
    assert issues[0]["level"] == "WARN"


def test_importo_coincidente_nessun_avviso():
    rt = parse_rt(_rt_xml(importo="237.00"))
    assert verifica_rt_per_deposito(rt, importo_atteso=237.0) == []


# --- Riepilogo busta --------------------------------------------------------------


def test_riepilogo_somma_frazionati_e_riconcilia():
    allegati = [
        ("RT_acconto.xml", _rt_xml(importo="100.00", iuv="IUV-A")),
        ("RT_saldo.xml", _rt_xml(importo="137.00", iuv="IUV-B")),
    ]
    esito = riepilogo_rt_allegate(allegati, importo_atteso=237.0)
    assert esito["totale_eseguito"] == 237.00
    assert len(esito["ricevute"]) == 2
    assert esito["issues"] == []


def test_riepilogo_totale_difforme_avvisa():
    esito = riepilogo_rt_allegate([("RT.xml", _rt_xml(importo="100.00"))], importo_atteso=237.0)
    assert any(i["code"] == "RT-TOTALE-DIFFORME" for i in esito["issues"])


def test_riepilogo_iuv_duplicato_avvisa():
    allegati = [
        ("RT_1.xml", _rt_xml(iuv="IUV-STESSO")),
        ("RT_2.xml", _rt_xml(iuv="IUV-STESSO")),
    ]
    esito = riepilogo_rt_allegate(allegati)
    assert any(i["code"] == "RT-DUPLICATA" for i in esito["issues"])


# --- Integrazione audit busta -----------------------------------------------------


def _pdf_minimo(tmp_path):
    pdf = tmp_path / "atto.pdf"
    pdf.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF"
    )
    return str(pdf)


def _busta_con_rt(tmp_path, rt_bytes: bytes, importo_cu: float) -> BustaTelematica:
    rt_file = tmp_path / "RT_contributo.xml"
    rt_file.write_bytes(rt_bytes)
    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="Iscrizione a ruolo - RG 1234/2024",
        tipo_atto="CITAZIONE",
        atto_principale=_pdf_minimo(tmp_path),
        allegati=[Allegato(percorso=str(rt_file), descrizione="Ricevuta telematica pagamento CU")],
        numero_rg="1234",
        anno_rg=2024,
        cf_mittente="RSSMRA80A01H501Z",
        operatore="Avv. Mario Rossi",
        contributo_unificato={"mode": "pagato", "importo": importo_cu, "resolved": True},
    )
    return BustaTelematica(dati)


def test_audit_busta_espone_rt_verificata(tmp_path):
    busta = _busta_con_rt(tmp_path, _rt_xml(importo="237.00"), importo_cu=237.0)
    audit = busta.audit_conformita_pst()
    pagamenti = audit["ricevute_pagamento"]
    assert len(pagamenti["ricevute"]) == 1
    assert pagamenti["ricevute"][0]["pagamento_eseguito"] is True
    assert pagamenti["totale_eseguito"] == 237.00
    assert not [i for i in audit["issues"] if str(i.get("code", "")).startswith("RT-")]


def test_audit_busta_avvisa_rt_esito_negativo_senza_bloccare(tmp_path):
    busta = _busta_con_rt(tmp_path, _rt_xml(esito="1", importo="0.00"), importo_cu=237.0)
    audit = busta.audit_conformita_pst()
    rt_issues = [i for i in audit["issues"] if str(i.get("code", "")).startswith("RT-")]
    assert any(i["code"] == "RT-ESITO-NEGATIVO" for i in rt_issues)
    assert all(i["level"] == "WARN" for i in rt_issues)


def test_audit_busta_avvisa_importo_difforme(tmp_path):
    busta = _busta_con_rt(tmp_path, _rt_xml(importo="98.00"), importo_cu=237.0)
    audit = busta.audit_conformita_pst()
    codes = [i.get("code") for i in audit["issues"]]
    assert "RT-TOTALE-DIFFORME" in codes
