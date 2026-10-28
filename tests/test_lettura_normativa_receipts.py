import hashlib
import json
from types import SimpleNamespace

import pytest

from lex.procedura_atti.lettura_fonti import _estrai, prepara_letture


def test_coda_deve_essere_letterale_e_non_una_parola_generica():
    text="Una norma con condizioni specifiche da leggere prima di formulare la risposta finale."
    with pytest.raises(ValueError):
        _estrai(json.dumps({"passaggi":["condizioni specifiche"],"fine":"finale."}),text)
    with pytest.raises(ValueError):
        _estrai(json.dumps({"passaggi":["condizioni specifiche"],"fine":"specifiche da leggere prima di formulare la risposta"}),text)
    tail=" ".join(text.split()[-8:])
    assert _estrai(json.dumps({"passaggi":["condizioni specifiche"],"fine":tail}),text)==["condizioni specifiche"]


def test_parti_contigue_e_impronta_del_testo_originale():
    text=("Condizione documentata senza modificare parole e senza saltare alcuna parte del testo. "*180)
    received=[]
    def model(system,prompt):
        part=prompt.split("Testo normativo da leggere:\n",1)[1]
        received.append(part)
        quote=part[:50]
        return json.dumps({"passaggi":[quote],"fine":" ".join(part.split()[-8:])}),"modello-unitario"
    original=SimpleNamespace(fonti={1:text})
    view,trace=prepara_letture(original,richiesta="Leggi le condizioni",chiama_modello=model,
        messaggio_caratteri=len(text)+500,budget_caratteri=6000,forza_parti=True)
    # Le prime chiamate coprono tutte le parti; un'eventuale chiamata successiva
    # seleziona nuovamente solo tra citazioni già lette, non riscrive il testo.
    parts=trace[0]["parti"]
    assert "".join(received[:len(parts)])==text
    assert parts[0]["inizio"]==0 and parts[-1]["fine"]==len(text)
    assert all(a["fine"]==b["inizio"] for a,b in zip(parts,parts[1:]))
    assert trace[0]["sha256_testo"]==hashlib.sha256(text.encode()).hexdigest()
    assert original.fonti[1]==text
    assert view.fonti[1]!=text
