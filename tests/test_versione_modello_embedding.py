"""«Indice vettoriale ignorato: versione del modello diversa» (collaudo 21/11/2026).

Con il PC carico /api/tags superava i 4 s, il ripiego su /api/show dava solo
``modified_at`` (una data) e il confronto con il digest dell'indice scartava la
ricerca semantica per sempre. Ora la data non vale come versione e una versione
non letta non si memorizza.
"""
from types import SimpleNamespace

import numpy as np

from lex.ricerca_giuridica import embedding as emb
from lex.ricerca_giuridica.ibrida import MotoreRicercaNormattiva

DIGEST = "85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1"


class _Risposta:
    def __init__(self, dati):
        self._dati = dati

    def raise_for_status(self):
        return None

    def json(self):
        return self._dati


def test_modified_at_non_e_una_versione_e_si_riprova(monkeypatch):
    import requests

    stato = {"tags_lento": True}

    def get(url, timeout):
        if stato["tags_lento"]:
            raise requests.Timeout("lento")
        return _Risposta({"models": [{"name": "embeddinggemma:300m", "digest": DIGEST}]})

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", lambda url, json, timeout: _Risposta({"modified_at": "2026-10-02T08:33:42+02:00"}))
    embedder = emb.OllamaEmbedder(modello="embeddinggemma:300m", url="http://ollama.prova:11434")
    assert embedder.versione() == ""  # la data non si scambia per la versione
    stato["tags_lento"] = False
    assert embedder.versione() == DIGEST  # niente memoria del fallimento


class _Indice:
    def __init__(self):
        self.meta = {"modello_versione": DIGEST}

    def verifica_modello(self, modello, versione=""):
        if versione and versione != DIGEST:
            return False, "versione del modello diversa"
        return True, ""


def _motore(versioni):
    motore = MotoreRicercaNormattiva.__new__(MotoreRicercaNormattiva)
    motore._indice = _Indice()
    motore._versione_verificata = False
    motore._motivo_semantica = ""
    motore.embedder = SimpleNamespace(modello="embeddinggemma:300m", versione=lambda: versioni.pop(0))
    motore._domande = SimpleNamespace(vettore=lambda domanda: np.ones(4, dtype=np.float32))
    return motore


def test_versione_non_letta_non_scarta_l_indice():
    motore = _motore(["", DIGEST])
    assert motore._vettore_domanda("responsabilità extracontrattuale") is None
    assert motore._indice is not None and "non verificata" in motore._motivo_semantica
    assert motore._vettore_domanda("responsabilità extracontrattuale") is not None
    assert motore._versione_verificata is True


def test_versione_davvero_diversa_scarta_l_indice():
    motore = _motore(["0" * 64])
    assert motore._vettore_domanda("art. 2043") is None
    assert motore._indice is None
