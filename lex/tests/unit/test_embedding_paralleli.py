"""Embedding in parallelo: stesso risultato e stesso ordine del percorso sequenziale."""

import threading

import numpy as np

from lex.ricerca_giuridica.embedding import OllamaEmbedder


def _finto(testi):
    vettori = np.asarray([[float(len(t)), float(sum(map(ord, t)) % 97), 1.0] for t in testi], dtype=np.float32)
    return vettori / np.linalg.norm(vettori, axis=1, keepdims=True)


def test_parallelo_preserva_ordine_e_valori(monkeypatch):
    chiamate = []
    lock = threading.Lock()

    def finto(self, testi):
        with lock:
            chiamate.append(len(testi))
        return _finto(testi)

    monkeypatch.setattr(OllamaEmbedder, "_embed_una_volta", finto)
    testi = [f"articolo {i} " * (i % 5 + 1) for i in range(37)]
    seq = OllamaEmbedder(modello="m", url="http://x", paralleli=1).embed(testi)
    par = OllamaEmbedder(modello="m", url="http://x", paralleli=4).embed(testi)
    assert np.allclose(seq, par)
    assert sorted(chiamate[1:]) == [7, 10, 10, 10]


def test_paralleli_da_variabile_ambiente(monkeypatch):
    monkeypatch.setenv("LEX_EMBED_PARALLELI", "3")
    assert OllamaEmbedder(modello="m", url="http://x").paralleli == 3
    monkeypatch.setenv("LEX_EMBED_PARALLELI", "abc")
    assert OllamaEmbedder(modello="m", url="http://x").paralleli == 1
