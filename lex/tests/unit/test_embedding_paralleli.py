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


def test_flusso_tiene_le_richieste_in_volo_e_preserva_ordine(monkeypatch):
    import time as _time

    from lex.ricerca_giuridica.indice_vettoriale import embed_in_flusso

    attive = {"ora": 0, "massimo": 0}
    lock = threading.Lock()

    def finto(self, testi):
        with lock:
            attive["ora"] += 1
            attive["massimo"] = max(attive["massimo"], attive["ora"])
        _time.sleep(0.02 if len(testi) % 2 else 0.005)  # richieste di durata diversa
        with lock:
            attive["ora"] -= 1
        return _finto(testi)

    monkeypatch.setattr(OllamaEmbedder, "_embed_una_volta", finto)
    emb = OllamaEmbedder(modello="m", url="http://x", paralleli=4)
    lotti = [[f"testo {i}-{j} " * (j + 1) for j in range(i % 3 + 1)] for i in range(25)]
    usciti = list(embed_in_flusso(emb, lotti, lambda voce: voce))
    assert [lotto for lotto, _ in usciti] == lotti
    for lotto, matrice in usciti:
        assert np.allclose(matrice, _finto(lotto))
    assert attive["massimo"] == 4


def test_costruzione_in_flusso_uguale_alla_sequenziale(tmp_path):
    import sqlite3

    from lex.ricerca_giuridica import indice_vettoriale as iv
    from lex.ricerca_giuridica.embedding import EmbedderFinto
    from lex.tests.unit.test_ricerca_giuridica_vettori import _importa, ARTICOLI
    from lex.normativa import normattiva_importer as imp

    class FintoParallelo(EmbedderFinto):
        paralleli = 3

    conn = sqlite3.connect(str(tmp_path / "n.db"))
    imp.ensure_schema(conn)
    _importa(conn, "a" * 8, "VIGENTE", ARTICOLI)
    velocita = []
    seq = iv.costruisci_indice(conn, tmp_path / "s", EmbedderFinto(64), batch=4)
    par = iv.costruisci_indice(conn, tmp_path / "p", FintoParallelo(64), batch=4, progresso=lambda a, b, v: velocita.append((a, v)))
    assert seq.nuovi == par.nuovi == 6
    for nome in ("vettori.i8", "scale.f32", "ids.i64", "impronte.u64"):
        assert (tmp_path / "s" / nome).read_bytes() == (tmp_path / "p" / nome).read_bytes()
    # ripresa: nulla da ricalcolare, la velocita' non conta i chunk gia' presenti
    velocita.clear()
    di_nuovo = iv.costruisci_indice(conn, tmp_path / "p", FintoParallelo(64), batch=4, progresso=lambda a, b, v: velocita.append((a, v)))
    assert di_nuovo.nuovi == 0 and di_nuovo.invariati == 6 and velocita == []
    conn.close()


class _Risposta:
    def __init__(self, codice):
        self.status_code = codice


def _errore_http(codice=500):
    import requests

    return requests.HTTPError(f"{codice} Server Error", response=_Risposta(codice))


def test_testo_anomalo_isolato_e_accorciato(monkeypatch):
    def finto(self, testi):
        if any("VELENO" in t for t in testi):
            raise _errore_http(500)
        return _finto(testi)

    monkeypatch.setattr(OllamaEmbedder, "_embed_una_volta", finto)
    testi = [f"testo {i}" for i in range(16)]
    testi[11] = "x" * 1000 + " VELENO"  # rifiutato intero, accettato accorciato a 800 caratteri
    emb = OllamaEmbedder(modello="m", url="http://x", paralleli=1, attesa_s=0)
    matrice = emb.embed_singolo(testi)
    assert matrice.shape[0] == 16
    assert np.allclose(np.delete(matrice, 11, axis=0), _finto([t for i, t in enumerate(testi) if i != 11]))
    assert np.allclose(matrice[11], _finto(["x" * 800])[0])
    assert emb.testi_ridotti == [(testi[11][:120], 1007, 800)]


def test_ollama_spento_non_divide(monkeypatch):
    import requests

    chiamate = []

    def finto(self, testi):
        chiamate.append(len(testi))
        raise requests.ConnectionError("rifiutata")

    monkeypatch.setattr(OllamaEmbedder, "_embed_una_volta", finto)
    emb = OllamaEmbedder(modello="m", url="http://x", tentativi=2, attesa_s=0)
    try:
        emb.embed_singolo(["a", "b", "c", "d"])
        raise AssertionError("doveva fallire")
    except RuntimeError:
        pass
    assert chiamate == [4, 4]


def test_modello_non_caricabile_non_divide(monkeypatch):
    import requests

    class _RispostaGuasto:
        status_code = 500
        text = '{"error":"llama-server process has terminated: signal: segmentation fault (core dumped)"}'

    chiamate = []

    def finto(self, testi):
        chiamate.append(len(testi))
        raise requests.HTTPError("500 Server Error", response=_RispostaGuasto())

    monkeypatch.setattr(OllamaEmbedder, "_embed_una_volta", finto)
    emb = OllamaEmbedder(modello="m", url="http://x", tentativi=2, attesa_s=0)
    try:
        emb.embed_singolo(["a", "b", "c", "d"])
        raise AssertionError("doveva fallire")
    except RuntimeError:
        pass
    assert chiamate == [4, 4]


def test_piu_istanze_a_turno(monkeypatch):
    import requests

    usati = []

    class R:
        status_code = 200

        def __init__(self, n):
            self.n = n

        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [[1.0, 0.0, 0.0]] * self.n}

    def post(url, json=None, timeout=None):
        usati.append(url.split("/api/")[0])
        return R(len(json["input"]))

    monkeypatch.setattr(requests, "post", post)
    emb = OllamaEmbedder(modello="m", url="http://127.0.0.1:11434, http://127.0.0.1:11435/api", paralleli=1)
    assert emb.url == "http://127.0.0.1:11434" and emb.urls[1] == "http://127.0.0.1:11435"
    for _ in range(4):
        emb.embed_singolo(["a", "b"])
    assert usati == ["http://127.0.0.1:11434", "http://127.0.0.1:11435"] * 2


def test_istanze_con_modello_diverso_rifiutate(monkeypatch):
    import requests

    class T:
        def __init__(self, digest):
            self.digest = digest

        def raise_for_status(self):
            pass

        def json(self):
            return {"models": [{"name": "m:latest", "digest": self.digest}]}

    monkeypatch.setattr(requests, "get", lambda url, timeout=None: T("aaa" if ":11434" in url else "bbb"))
    emb = OllamaEmbedder(modello="m", url="http://127.0.0.1:11434,http://127.0.0.1:11435")
    try:
        emb.versione()
        raise AssertionError("doveva rifiutare")
    except RuntimeError as exc:
        assert "versione diversa" in str(exc)
    from lex.ricerca_giuridica.embedding import IstanzeOllamaDiverse
    assert issubclass(IstanzeOllamaDiverse, RuntimeError)
