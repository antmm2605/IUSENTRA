"""Provenienza delle uscite AI e cancello di ancoraggio (valori proposti dal modello)."""

from __future__ import annotations

from pct.provenienza_ai import ESITO_BLOCCATO, Provenienza, cancello_ancoraggio, impronta, verifica_sigillo

TESTO = "Il decreto del 10 settembre 2026 ingiunge il pagamento di euro 1.234,56 a Verdi Giulia. R.G. 1234/2026."


def test_valori_ancorati_passano():
    esito = cancello_ancoraggio({"data": "10/09/2026", "importo": "1.234,56", "parte": "Verdi Giulia", "rg": "1234/2026"}, TESTO)
    assert esito.ammesso, esito.to_dict()


def test_data_o_numero_inventati_si_bloccano():
    esito = cancello_ancoraggio({"data": "11/09/2026", "importo": "1.234,57", "rg": "3420"}, TESTO)
    assert not esito.ammesso
    assert {c.campo for c in esito.bloccati} == {"data", "importo", "rg"}
    assert all(c.esito == ESITO_BLOCCATO for c in esito.bloccati)


def test_numero_a_cavallo_di_due_numeri_non_passa():
    # «342» compare solo unendo le cifre di «1234» e «2026»: non è nel testo.
    assert not cancello_ancoraggio({"numero": "342"}, "R.G. 1234/2026 del 2026").ammesso


def test_registro_ufficiale_ancora_i_valori_assenti_dal_testo():
    esito = cancello_ancoraggio({"ufficio": "Tribunale di Palmi"}, TESTO, registri={"ufficio": ["Tribunale di Palmi"]})
    assert esito.ammesso
    assert not cancello_ancoraggio({"ufficio": "Tribunale di Palmi"}, TESTO).ammesso


def test_sigillo_riconosce_le_modifiche():
    record = Provenienza("catalogo.seconda_lettura", "spark", "v1", impronta(TESTO), citazione="Il decreto").to_dict()
    assert verifica_sigillo(record)
    record["modello"] = "altro"
    assert not verifica_sigillo(record)


def test_catalogo_lex_registra_provenienza():
    from pct.document_intelligence.catalog_lex import applica_esito, leggi_con_lex, voci_catalogo
    from pct.document_intelligence.models import DocumentCatalogAssignment

    voci = voci_catalogo()
    voce = next(v for v in voci if v.label == "Decreto ingiuntivo")
    testo = "TRIBUNALE DI MILANO\nDECRETO INGIUNTIVO N. 12/2026\nIl giudice ingiunge a Blu Franco di pagare."
    esito = leggi_con_lex(testo, genera=lambda domanda, schema: '{"etichetta": "Decreto ingiuntivo", "citazione": "DECRETO INGIUNTIVO N. 12/2026", "motivo": "titolo"}', voci=voci)
    assert esito.stato == "scelta" and esito.sha_input == impronta(testo[:len(testo)])
    assignment = DocumentCatalogAssignment(
        id="a1", tenant_id="t", fascicolo_id="f", document_id="d", document_ai_id=None, document_version_id=None,
        document_sha256="x", profile_id=None, legal_area=None, legal_branch=None, legal_subfamily=None, jurisdiction=None,
        rite=None, proceeding_phase=None, document_nature=voce.nature, document_label=voce.label, document_section=voce.section,
        deposit_role=voce.deposit_role, deposit_candidate=True, status="review_required", confidence=55,
        source_state="automatic", resolver_version="v", rule_set_id=None, reason="",
    )
    aggiornato, _candidati, _evidenze = applica_esito(assignment, [], [], esito, modello="maternion/spark-x2.5:4b")
    provenienza = aggiornato.metadata["lex_lettura"]["provenienza"]
    assert provenienza["modello"] == "maternion/spark-x2.5:4b"
    assert provenienza["cancello"]["ammesso"] is True
    assert verifica_sigillo(provenienza)
