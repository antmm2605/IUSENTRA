"""Catalogazione documentale: un solo calcolo dei conteggi e la regola della certezza (richiesta del 19/11/2026).

Caso reale ridotto (9A681FDF): 45 file nel fascicolo, di cui 2 bozze dello studio; 41 proposte con affidabilità
≥ 90 e prova letta dal contenuto, 2 da verificare. Prima il pannello diceva «Automatici 0 · Proposti 41», il filtro
«Tutti gli stati 45» e il quadro «45 documenti · 4 da classificare».
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.document_intelligence.certezza_lettura import (
    STATO_AUTOMATICO,
    motivo_da_confermare,
    riepilogo_catalogo,
    stato_catalogo,
)


def test_proposta_certa_dal_contenuto_e_catalogata_in_automatico():
    assert stato_catalogo("proposed", 96, ha_prova=True) == STATO_AUTOMATICO
    assert stato_catalogo("proposed", 90, ha_prova=True) == STATO_AUTOMATICO
    # Sotto la soglia o senza prova: resta una proposta, con il motivo.
    assert stato_catalogo("proposed", 89, ha_prova=True) == "proposed"
    assert motivo_da_confermare("proposed", 89, ha_prova=True) == "affidabilità 89% sotto la soglia di certezza del 90%"
    assert stato_catalogo("proposed", 99, ha_prova=False) == "proposed"
    assert motivo_da_confermare("proposed", 99, ha_prova=False) == "manca una prova letta dal contenuto"
    assert motivo_da_confermare("proposed", 95, ha_prova=True) == ""
    # Le decisioni dell'avvocato e le voci da rivedere non cambiano mai.
    for stato in ("confirmed", "overridden", "review_required"):
        assert stato_catalogo(stato, 99, ha_prova=True) == stato


def test_riepilogo_unico_somma_sempre_i_documenti():
    stati = [STATO_AUTOMATICO] * 41 + ["review_required"] * 2
    r = riepilogo_catalogo(stati)
    assert r == {"documenti": 43, "catalogati": 41, "automatici": 41, "confermati": 0, "proposti": 0,
                 "da_verificare": 2, "in_attesa": 0}
    misti = riepilogo_catalogo([STATO_AUTOMATICO, "confirmed", "overridden", "proposed", "review_required", None, "non_catalogato"])
    assert misti["documenti"] == misti["catalogati"] + misti["da_verificare"] + misti["in_attesa"]
    assert misti["catalogati"] == misti["automatici"] + misti["confermati"] + misti["proposti"] == 4
    assert misti["in_attesa"] == 2


def test_quadro_e_lettura_contano_senza_le_bozze_e_con_la_stessa_regola(monkeypatch):
    from web.services import catalogo_conteggi_runtime as conteggi
    from web.services import fascicolo_quadro_runtime as quadro

    documenti = [SimpleNamespace(id=f"D{i}", fonte_documento="IMPORT_ESTERNO") for i in range(43)]
    documenti += [SimpleNamespace(id="B1", fonte_documento="BOZZA_PASSO"), SimpleNamespace(id="B2", fonte_documento="BOZZA_PASSO")]
    fascicolo = SimpleNamespace(id="9A681FDF", documenti=documenti)
    assegnazioni = {f"D{i}": SimpleNamespace(id=f"A{i}", status="proposed" if i < 41 else "review_required", confidence=95,
                                             metadata={}) for i in range(43)}
    monkeypatch.setattr("web.services.react_fascicoli_bridge._sql_document_catalog_by_id", lambda _f: assegnazioni)
    monkeypatch.setattr(conteggi, "voci_con_prova", lambda _fid: {f"A{i}" for i in range(43)})
    r = conteggi.riepilogo_fascicolo(fascicolo)
    assert (r["documenti"], r["automatici"], r["proposti"], r["da_verificare"]) == (43, 41, 0, 2)
    assert quadro._numero_documenti(fascicolo) == 43
    assert quadro.documenti_da_classificare(fascicolo) == 2
