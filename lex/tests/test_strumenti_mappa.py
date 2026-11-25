"""La mappa degli strumenti di Lex resta allineata al codice.

Fallisce se: una sorgente del registro operativo, un adattatore del retrieval, un tool del registro Lex o un
calcolatore nuovo non è in nessuna scheda né in FUORI_MAPPA; una scheda nomina qualcosa che non esiste più;
mappa.json non coincide con la rigenerazione; l'esempio di una scheda non è una chiamata eseguibile.
"""
from __future__ import annotations

import json

import pytest

from lex.strumenti import genera
from lex.strumenti.mappa import FILE_MAPPA, copertura, mappa, valida_chiamata
from lex.strumenti.schede import FUORI_MAPPA, SCHEDE


def test_ogni_fonte_del_codice_e_in_mappa_e_nessuna_voce_morta():
    cop = copertura()
    problemi = genera.lacune(cop)
    assert not problemi, "\n".join(problemi)
    assert cop["adattatori"]["nel_codice"] == cop["adattatori"]["in_mappa"]


def test_mappa_json_aggiornata():
    assert FILE_MAPPA.read_text(encoding="utf-8") == genera.testo_mappa(), "eseguire python -m lex.strumenti.genera"


def test_una_sorgente_nuova_non_in_mappa_fa_fallire(monkeypatch):
    from lex.strumenti import mappa as modulo

    vere = modulo.sorgenti_registro()
    monkeypatch.setattr(modulo, "sorgenti_registro", lambda: {**vere, "sorgente_nuova": object()})
    assert copertura()["sorgenti_registro"]["mancanti"] == ["sorgente_nuova"]


def test_nomi_unici_e_fuori_mappa_motivati():
    nomi = [s.nome for s in SCHEDE]
    assert len(nomi) == len(set(nomi))
    assert all(motivo.strip() for voci in FUORI_MAPPA.values() for motivo in voci.values())


@pytest.mark.parametrize("voce", mappa()["strumenti"], ids=lambda v: v["nome"])
def test_ogni_scheda_ha_contenuto_funzioni_esempio(voce):
    assert voce["contenuto"] and voce["esempio"] and voce["tempo_tipico"]
    assert voce["funzioni"] and all(f["esiste"] for f in voce["funzioni"])


def test_valida_chiamata_parametri():
    assert valida_chiamata("norma_testo_vigente", {"atto": "c.c.", "articolo": "2051"}) == []
    assert valida_chiamata("norma_testo_vigente", {"atto": "d.lgs. 28/2010", "articolo": "5", "alla_data": "01/02/2024"}) == []
    assert valida_chiamata("norma_testo_vigente", {"atto": "codice inventato", "articolo": "1"})
    assert valida_chiamata("norma_testo_vigente", {"articolo": "1"})  # manca l'atto
    assert valida_chiamata("agenda_udienze", {"dal": "2026-01-01"})  # data non italiana
    assert valida_chiamata("agenda_udienze", {"dal": "31/02/2026"})  # data inesistente
    assert valida_chiamata("strumento_inventato", {})
    assert valida_chiamata("calcolo", {"strumento": "interessi", "campi": {"int_tipo": "legali", "int_capitale": 1000.0,
                                                                          "int_data_inizio": "01/01/2024"}}) == []
    assert valida_chiamata("calcolo", {"strumento": "interessi", "campi": {"campo_inventato": 1}})
    assert valida_chiamata("calcolo", {"strumento": "interessi", "campi": {"int_tipo": "inventato"}})


def test_calcolatori_con_metodo_reale():
    calc = mappa()["calcolatori"]
    assert len(calc) >= 70
    assert all(v["metodo_esiste"] for v in calc.values()), [k for k, v in calc.items() if not v["metodo_esiste"]]


def test_scelta_sugli_esempi_certi():
    from lex.strumenti.scelta import scegli

    assert [c.to_dict() for c in scegli("Cosa dice il secondo comma dell'art. 2051 c.c.?")] == [
        {"nome": "norma_testo_vigente", "parametri": {"atto": "c.c.", "articolo": "2051", "comma": "2"}}]
    assert scegli("Che sentenze ci sono sull'art. 1385 c.c.?")[0].to_dict() == {
        "nome": "sentenze_per_norma", "parametri": {"norma": "art. 1385 c.c."}}
    c = scegli("Trovami Cass. civ. sez. III n. 9449/2016.")[0]
    assert (c.nome, c.parametri["numero"], c.parametri["anno"], c.parametri["corte"]) == (
        "giurisprudenza_cassazione_consulta", 9449, 2016, "cassazione")
    assert scegli("Calcola gli interessi legali su 12.000 euro dal 01/03/2024 a oggi.")[0].parametri == {
        "strumento": "interessi", "campi": {"int_tipo": "legali", "int_capitale": 12000.0, "int_data_inizio": "01/03/2024"}}
    assert scegli("Grazie, a dopo") == []
    for voce in mappa()["strumenti"]:
        for c in scegli(voce["esempio"]):
            assert valida_chiamata(c.nome, c.parametri) == [], (voce["nome"], c)


def test_guida_del_retrieval(monkeypatch):
    from lex.contracts import LexRequest
    from lex.retrieval.source_router import SourceRouter
    from lex.router import LexRouter

    def fonti(q, fascicolo=None):
        r = LexRequest(tenant_id="t", user_id="u", session_id="s", query=q, fascicolo_id=fascicolo)
        return [f.__class__.__name__ for f in SourceRouter().resolve(r, {}, LexRouter().resolve_workflow(r))]

    monkeypatch.setenv("LEX_MAPPA_STRUMENTI", "1")
    assert fonti("Cosa dice l'art. 2051 c.c.?") == ["NormativeSource", "OfficialWebSource"]
    assert fonti("Cass. civ. sez. III n. 9449/2016") == ["GiurisprudenzaSource", "OfficialWebSource"]
    domanda_generica = fonti("Responsabilità del custode per danni da cose in custodia")
    assert "GiurisprudenzaSource" in domanda_generica and "LegalUpdatesSource" in domanda_generica
    # Dentro un fascicolo la mappa non tocca le fonti.
    assert "FascicoliSource" in fonti("Cosa dice l'art. 2051 c.c.?", fascicolo="F1")
    monkeypatch.setenv("LEX_MAPPA_STRUMENTI", "0")
    assert "LegalUpdatesSource" in fonti("Cosa dice l'art. 2051 c.c.?")


def test_descrizione_per_il_modello_contiene_tutti_gli_strumenti():
    from lex.strumenti.mappa import per_il_modello

    testo = per_il_modello()
    assert all(f"- {s['nome']}(" in testo for s in mappa()["strumenti"])
    assert json.loads(FILE_MAPPA.read_text(encoding="utf-8"))["schema"] == "iusentra.lex_mappa_strumenti.v1"
