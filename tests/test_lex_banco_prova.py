"""Banco di prova di Lex (tests/lex_banco): domande reali dell'avvocato sui dati dello studio.

La soglia (`tests/lex_banco/soglia.json`) elenca le domande già risolte: nessuna
modifica può farne sbagliare una. Quando Lex migliora, la soglia si alza con
`python scripts/lex_banco_prova.py --aggiorna-soglia`.
"""

from __future__ import annotations

from datetime import date

from tests.lex_banco.valutazione import carica_domande, carica_soglia, esegui_banco, forme_data, valuta

CATEGORIE = {"quando", "forma", "conteggio", "rg", "udienza", "settimana", "omonimi", "assenza", "fascicolo", "conferma"}


def _attesi(caso: dict) -> list[str]:
    return [*caso.get("deve_contenere", []), *caso.get("almeno_uno", []), *caso.get("non_deve_contenere", [])]


def test_domande_del_banco_sono_ben_formate():
    dati = carica_domande()
    casi = dati["domande"]
    ids = [caso["id"] for caso in casi]
    assert len(casi) >= 40
    assert len(ids) == len(set(ids))
    assert {caso["categoria"] for caso in casi} == CATEGORIE
    for caso in casi:
        assert caso["domanda"].strip() and caso["risposta_attesa"].strip(), caso["id"]
        assert caso.get("deve_contenere") or caso.get("almeno_uno"), caso["id"]
        for atteso in _attesi(caso):
            if atteso.startswith("data:"):
                date.fromisoformat(atteso[5:])
        assert set(caso.get("solo", [])) <= set(dati["date_clienti"]), caso["id"]
    assert set(carica_soglia().get("superate", [])) <= set(ids)


def test_valutazione_accetta_solo_date_italiane_e_isola_il_cliente():
    assert "20 ottobre 2026" in forme_data("2026-10-20") and "20/10/2026" in forme_data("2026-10-20")
    caso = {"id": "T", "categoria": "quando", "domanda": "?", "deve_contenere": ["data:2026-10-20"], "solo": ["Gramuglia"]}
    date_clienti = {"Gramuglia": ["2026-10-20"], "Esposito": ["2026-10-07"]}
    assert valuta(caso, "Entro il 20 ottobre 2026 (Gramuglia c. INPS).", [], date_clienti).superata
    assert valuta(caso, "Entro il 20/10/2026.", [], date_clienti).superata
    assert not valuta(caso, "Entro il 2026-10-20.", [], date_clienti).superata
    elenco = valuta(caso, "Scadenze: 7 ottobre 2026, 20 ottobre 2026.", [], date_clienti)
    assert not elenco.superata and "riporta date di Esposito: 2026-10-07" in elenco.motivi
    assert not valuta(caso, "20 ottobre 2026. Non ho trovato dati", ["Non ho trovato dati"], date_clienti).superata


def test_banco_di_prova_nessuna_regressione():
    soglia = set(carica_soglia().get("superate", []))
    esiti = {esito.id: esito for esito in esegui_banco()}
    perse = {
        id_caso: f"{esiti[id_caso].domanda} → {'; '.join(esiti[id_caso].motivi)}"
        for id_caso in sorted(soglia)
        if not esiti[id_caso].superata
    }
    assert not perse, f"Domande di Lex che prima erano giuste e ora sbagliano: {perse}"
