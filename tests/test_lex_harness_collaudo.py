"""Collaudo di Lex sulla batteria di domande reali (tests/lex_collaudo/domande.json), con punteggio automatico.

Ogni risposta attesa è scritta come la scriverebbe l'avvocato, sulla norma vigente: conclusione, norme da citare,
espressioni vietate. La soglia di chiusura è il 90% di risposte corrette e nessuna norma non verificata.
"""
from __future__ import annotations

import pytest

from lex.harness.http import payload_harness
from lex.harness.norme import ISTANTANEA
from tests.lex_collaudo.punteggio import carica, riepilogo, valuta

pytestmark = pytest.mark.skipif(not ISTANTANEA.is_file(), reason="istantanea delle norme non generata")


def _certa(domanda: str) -> str:
    from lex.risposte_certe import risposta_certa

    esito = risposta_certa(domanda)
    if esito is None:
        return ""
    fonti = "\n".join(f"- {f['title']}: {f['url']}" for f in esito.fonti)
    return esito.testo + (f"\n\nFonti:\n{fonti}" if fonti else "")


def _risposta(domanda: dict) -> tuple[str, bool]:
    payload = payload_harness(domanda["domanda"], risposta_certa=_certa)
    return (str(payload.get("answer") or "") if payload else ""), payload is None


def test_batteria_almeno_90_per_cento_e_nessuna_norma_inventata():
    esiti = []
    for domanda in carica():
        testo, operativa = _risposta(domanda)
        esiti.append(valuta(domanda, testo, operativa=operativa))
    giuste = sum(1 for e in esiti if e.corretta)
    print(riepilogo(esiti))
    assert not [e.id for e in esiti if e.inventate], riepilogo(esiti)
    assert giuste / len(esiti) >= 0.9, riepilogo(esiti)


def test_ferrandina_risolto_per_intero():
    domanda = next(d for d in carica() if d["id"] == "ferrandina")
    testo, _ = _risposta(domanda)
    esito = valuta(domanda, testo)
    assert esito.corretta, esito
    for sezione in ("**Cosa ho capito**", "**Conclusione**", "**Come e perché**", "**Termini**", "**Cosa fare**",
                    "**Dubbi e dati da completare**", "**Norme applicate**", "**Bozza dell'atto**"):
        assert sezione in testo


def test_casi_avvocato_almeno_90_per_cento():
    from tests.lex_collaudo.punteggio import carica_casi, riepilogo_casi, valuta_caso

    esiti = []
    for caso in carica_casi():
        payload = payload_harness(caso["domanda"], risposta_certa=_certa)
        esiti.append(valuta_caso(caso, str(payload.get("answer") or "") if payload else ""))
    print(riepilogo_casi(esiti))
    assert all(e.criteri["inventate"] for e in esiti), riepilogo_casi(esiti)
    assert sum(1 for e in esiti if e.corretto) / len(esiti) >= 0.9, riepilogo_casi(esiti)
