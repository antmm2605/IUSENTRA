"""Test dell'indice vettoriale e della ricerca ibrida (modulo 2B), con embedding finto e senza rete."""

from __future__ import annotations

import io
import json
import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest

from lex.normativa import normattiva_importer as imp
from lex.ricerca_giuridica import indice_vettoriale as iv
from lex.ricerca_giuridica.embedding import EmbedderDomande, EmbedderFinto, OllamaEmbedder, PREFISSO_DOMANDA
from lex.ricerca_giuridica.ibrida import MotoreRicercaNormattiva, fondi_rrf
from lex.ricerca_giuridica.indice_fts import sincronizza_fts
from lex.ricerca_giuridica.testo import analizza_domanda

ARTICOLI = [
    ("2043", "Risarcimento per fatto illecito", "Qualunque fatto doloso o colposo che cagiona ad altri un danno ingiusto obbliga a risarcire il danno."),
    ("1453", "Risoluzione per inadempimento", "Nei contratti con prestazioni corrispettive l'altro contraente puo chiedere la risoluzione del contratto per inadempimento."),
    ("2946", "Prescrizione ordinaria", "I diritti si estinguono per prescrizione con il decorso di dieci anni."),
    ("1490", "Garanzia per i vizi", "Il venditore deve garantire che la cosa venduta sia immune da vizi."),
    ("1321", "Nozione di contratto", "Il contratto e l'accordo di due o piu parti per costituire regolare o estinguere un rapporto giuridico patrimoniale."),
    ("2697", "Onere della prova", "Chi vuol far valere un diritto in giudizio deve provare i fatti che ne costituiscono il fondamento."),
]


class Contatore(EmbedderFinto):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.testi = 0
        self.chiamate = 0
        self.guasta_dopo: int | None = None

    def embed(self, testi):
        self.chiamate += 1
        if self.guasta_dopo is not None and self.chiamate > self.guasta_dopo:
            raise RuntimeError("rete caduta")
        self.testi += len(testi)
        return super().embed(testi)


def _importa(conn, sha, vigenza, articoli):
    rec = imp.DocumentRecord(
        collection_name="t", zip_path="t.zip", xml_entry=f"{sha}.xml", tipo_atto="CODICE", numero="262",
        data_atto="1942-03-16", data_pubblicazione="1942-03-16", titolo="Codice civile", urn=f"urn:{sha}",
        redazione_id=None, vigenza=vigenza, xml_sha256=sha, text_content="", topics=[], relevance_score=5.0,
        is_relevant=True, articles=[imp.ArticleRecord(n, r, f"Art. {n}. {r}. {t}", [], 1.0) for n, r, t in articoli],
    )
    doc_id = imp.insert_document(conn, rec, store_full_text=False)
    imp.insert_articles_and_chunks(conn, doc_id, rec, jsonl_file=io.StringIO(), max_chunk_chars=1800, only_relevant_articles=False)
    conn.commit()


@pytest.fixture()
def conn(tmp_path):
    c = sqlite3.connect(str(tmp_path / "n.db"))
    imp.ensure_schema(c)
    _importa(c, "a" * 8, "VIGENTE", ARTICOLI)
    yield c
    c.close()


def _n_chunk(conn):
    return conn.execute("SELECT COUNT(*) FROM normative_chunks").fetchone()[0]


def test_costruzione_e_metadati(conn, tmp_path):
    emb = Contatore(64)
    esito = iv.costruisci_indice(conn, tmp_path / "v", emb, batch=4)
    assert esito.nuovi == _n_chunk(conn) == 6 and esito.righe == 6
    indice = iv.IndiceVettoriale.apri(tmp_path / "v")
    assert indice.dimensioni == 64 and indice.righe == 6
    assert indice.meta["modello"] == emb.modello and indice.meta["formato"] == iv.FORMATO
    assert indice.meta["analizzatore"] and indice.meta["creato"] and indice.meta["chunk_totali"] == 6
    assert (tmp_path / "v" / "vettori.i8").stat().st_size == 6 * 64


def test_quantizzazione_int8_conserva_il_coseno():
    rng = np.random.default_rng(1)
    m = rng.normal(size=(20, 64)).astype(np.float32)
    valori, scale = iv.quantizza(m)
    ricostruiti = valori.astype(np.float32) * scale[:, None]
    n = m / np.linalg.norm(m, axis=1, keepdims=True)
    assert valori.dtype == np.int8
    assert float(np.abs(ricostruiti - n).max()) < 0.02


def test_ricerca_top_k_esatta(conn, tmp_path):
    emb = Contatore(64)
    iv.costruisci_indice(conn, tmp_path / "v", emb)
    indice = iv.IndiceVettoriale.apri(tmp_path / "v")
    domanda = "danno ingiusto fatto illecito risarcire"
    q = emb.embed([PREFISSO_DOMANDA + domanda])[0]
    trovati = indice.cerca(q, k=3, blocco=2)  # blocchi piccoli: prova la fusione dei blocchi
    ids = {r[0]: r for r in conn.execute("SELECT c.id, a.article_number FROM normative_chunks c JOIN normative_articles a ON a.id=c.article_id")}
    assert ids[trovati[0][0]][1] == "2043"
    punti = [p for _, p in trovati]
    assert punti == sorted(punti, reverse=True) and len(trovati) == 3
    # riferimento: ricerca esatta in numpy sui vettori ricostruiti
    mappe = indice._carica()
    pieno = (mappe["vettori"].astype(np.float32) * mappe["scale"][:, None]) @ q
    atteso = [int(mappe["ids"][i]) for i in np.argsort(-pieno)[:3]]
    assert [i for i, _ in trovati] == atteso
    assert indice.cerca(q, k=3, blocco=100000) == trovati


def test_ripresa_da_checkpoint(conn, tmp_path):
    emb = Contatore(64)
    emb.guasta_dopo = 2  # 2 batch da 2 chunk, poi la rete cade
    with pytest.raises(RuntimeError):
        iv.costruisci_indice(conn, tmp_path / "v", emb, batch=2)
    parziale = iv.IndiceVettoriale.apri(tmp_path / "v")
    assert parziale.righe == 4
    emb2 = Contatore(64)
    esito = iv.costruisci_indice(conn, tmp_path / "v", emb2, batch=2)
    assert esito.invariati == 4 and esito.nuovi == 2 and emb2.testi == 2
    assert iv.IndiceVettoriale.apri(tmp_path / "v").righe == 6


def test_ripresa_dopo_scrittura_troncata(conn, tmp_path):
    iv.costruisci_indice(conn, tmp_path / "v", Contatore(64), massimo=3, batch=3)
    with (tmp_path / "v" / "ids.i64").open("ab") as f:  # un file piu' lungo degli altri: blocco incompleto
        f.write(b"\x07" * 8)
    emb = Contatore(64)
    iv.costruisci_indice(conn, tmp_path / "v", emb)
    indice = iv.IndiceVettoriale.apri(tmp_path / "v")
    assert indice.righe == 6 and emb.testi == 3
    assert len(np.fromfile(tmp_path / "v" / "ids.i64", dtype=np.int64)) == 6


def test_aggiornamento_incrementale(conn, tmp_path):
    iv.costruisci_indice(conn, tmp_path / "v", Contatore(64))
    emb = Contatore(64)
    esito = iv.costruisci_indice(conn, tmp_path / "v", emb)
    assert (esito.nuovi, esito.ricalcolati, esito.eliminati, esito.invariati) == (0, 0, 0, 6) and emb.testi == 0

    conn.execute("UPDATE normative_chunks SET chunk_text = 'Art. 2946. Prescrizione. I diritti si estinguono in cinque anni.' WHERE id = (SELECT c.id FROM normative_chunks c JOIN normative_articles a ON a.id=c.article_id WHERE a.article_number='2946')")
    conn.execute("DELETE FROM normative_chunks WHERE id = (SELECT c.id FROM normative_chunks c JOIN normative_articles a ON a.id=c.article_id WHERE a.article_number='1490')")
    _importa(conn, "b" * 8, "ORIGINALE", [("2043", "Risarcimento per fatto illecito", "Testo originario del danno ingiusto.")])
    conn.commit()
    emb = Contatore(64)
    esito = iv.costruisci_indice(conn, tmp_path / "v", emb)
    assert (esito.nuovi, esito.ricalcolati, esito.eliminati) == (1, 1, 1) and emb.testi == 2
    indice = iv.IndiceVettoriale.apri(tmp_path / "v")
    mappe = indice._carica()
    assert int((mappe["ids"] < 0).sum()) == 1
    # il chunk eliminato non compare mai nei risultati
    q = emb.embed([PREFISSO_DOMANDA + "vizi della cosa venduta garanzia venditore"])[0]
    risultati = {i for i, _ in indice.cerca(q, k=50)}
    assert len(risultati) == _n_chunk(conn) == 6
    assert risultati == {r[0] for r in conn.execute("SELECT id FROM normative_chunks")}


def test_modello_diverso_rifiutato_in_costruzione_e_ignorato_in_ricerca(conn, tmp_path, caplog):
    iv.costruisci_indice(conn, tmp_path / "v", Contatore(64))
    with pytest.raises(iv.IndiceIncompatibile):
        iv.costruisci_indice(conn, tmp_path / "v", Contatore(32))
    sincronizza_fts(conn)
    conn.commit()
    with caplog.at_level("WARNING"):
        motore = MotoreRicercaNormattiva(tmp_path / "n.db", tmp_path / "v", embedder=Contatore(32))
    assert not motore.stato()["semantica_attiva"] and "ignorato" in motore.stato()["motivo_semantica"]
    assert any("ignorato" in r.message for r in caplog.records)
    ris = motore.cerca("risarcimento danno ingiusto", limite=3)
    assert ris and ris[0]["ricerca"]["rango_semantico"] == 0  # solo lessicale, nessun vettore incompatibile


def test_versione_modello_diversa_ignorata(conn, tmp_path):
    class V2(Contatore):
        def versione(self):
            return "v2"

    iv.costruisci_indice(conn, tmp_path / "v", Contatore(64))
    sincronizza_fts(conn)
    meta = json.loads((tmp_path / "v" / "meta.json").read_text())
    meta["modello_versione"] = "v1"
    (tmp_path / "v" / "meta.json").write_text(json.dumps(meta))
    motore = MotoreRicercaNormattiva(tmp_path / "n.db", tmp_path / "v", embedder=V2(64))
    motore.cerca("risarcimento danno", limite=3)
    assert not motore.stato()["semantica_attiva"] and "versione" in motore.stato()["motivo_semantica"]


def test_dimensioni_domanda_errate(conn, tmp_path):
    iv.costruisci_indice(conn, tmp_path / "v", Contatore(64))
    with pytest.raises(iv.IndiceIncompatibile):
        iv.IndiceVettoriale.apri(tmp_path / "v").cerca(np.ones(32, dtype=np.float32))


def test_rrf_pertinenza_e_vigente():
    analisi = analizza_domanda("responsabilita per danno")
    lessicali = [SimpleNamespace(chunk_id=1, bm25=-3.0), SimpleNamespace(chunk_id=2, bm25=-2.0), SimpleNamespace(chunk_id=3, bm25=-1.0)]
    semantici = [(2, 0.9), (4, 0.8), (1, 0.7)]
    info = {
        1: ("2043", "CC", "", "", "VIGENTE", "cc", 1),
        2: ("1453", "CC", "", "", "VIGENTE", "cc", 1),
        3: ("2946", "CC", "", "", "VIGENTE", "cc", 1),
        4: ("1490", "CC", "", "", "VIGENTE", "cc", 1),
    }
    ris = fondi_rrf(lessicali, semantici, info, analisi=analisi, esatti=set())
    atteso = {1: 1 / 61 + 1 / 63, 2: 1 / 62 + 1 / 61, 3: 1 / 63, 4: 1 / 62}
    for r in ris:
        assert r.rrf == pytest.approx(atteso[r.chunk_id])
    assert [r.chunk_id for r in ris] == [2, 1, 4, 3]  # presente in entrambe le liste batte presente in una
    # a pari pertinenza vince la VIGENTE; una versione ORIGINALE non supera la pertinenza
    info2 = dict(info)
    info2[5] = ("2043", "CC", "", "", "ORIGINALE", "cc-orig", 1)
    info2[6] = ("2043", "CC", "", "", "VIGENTE", "cc-vig", 1)
    ris2 = fondi_rrf([SimpleNamespace(chunk_id=5, bm25=-1.0)], [(6, 0.5)], info2, analisi=analisi, esatti=set())
    assert ris2[0].chunk_id == 6
    # filtro di vigenza
    assert [r.chunk_id for r in fondi_rrf(lessicali, semantici, info2, analisi=analisi, esatti=set(), vigenza="ORIGINALE")] == []


def test_ibrida_end_to_end(conn, tmp_path):
    iv.costruisci_indice(conn, tmp_path / "v", Contatore(64))
    sincronizza_fts(conn)
    conn.commit()
    motore = MotoreRicercaNormattiva(tmp_path / "n.db", tmp_path / "v", embedder=Contatore(64))
    assert motore.stato()["semantica_attiva"]
    ris = motore.cerca("Chi cagiona un danno ingiusto deve risarcirlo?", limite=3)
    assert "2043" in str(ris[0])
    assert ris[0]["ricerca"]["rango_semantico"] >= 1 and ris[0]["ricerca"]["rango_lessicale"] >= 1
    lessicale = motore.cerca("danno ingiusto", limite=3, modalita="lessicale")
    assert lessicale and lessicale[0]["ricerca"]["rango_semantico"] == 0


def test_embedder_domande_pausa_dopo_errore():
    class Rotto:
        modello = "x"
        chiamate = 0

        def embed(self, t):
            self.chiamate += 1
            raise RuntimeError("giu")

    r = Rotto()
    d = EmbedderDomande(r, pausa_dopo_errore_s=60)
    for _ in range(3):
        with pytest.raises(Exception):
            d.vettore("q")
    assert r.chiamate == 1


def test_ollama_retry(monkeypatch):
    import requests

    chiamate = []

    class Risposta:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [[3.0, 4.0]]}

    def finto_post(url, json=None, timeout=None):
        chiamate.append(url)
        if len(chiamate) < 3:
            raise requests.ConnectionError("giu")
        return Risposta()

    monkeypatch.setattr(requests, "post", finto_post)
    monkeypatch.setattr("time.sleep", lambda s: None)
    v = OllamaEmbedder(modello="m", url="http://x:1/api/embed", tentativi=3).embed(["a"])
    assert len(chiamate) == 3 and chiamate[0] == "http://x:1/api/embed"
    assert v[0] == pytest.approx([0.6, 0.8])


def test_cli_info(conn, tmp_path, capsys):
    iv.costruisci_indice(conn, tmp_path / "v", Contatore(64))
    assert iv.main(["info", "--out", str(tmp_path / "v")]) == 0
    assert "righe attive: 6 su 6" in capsys.readouterr().out
    assert iv.main(["info", "--out", str(tmp_path / "vuoto")]) == 1


def test_embedder_domande_riscalda_dopo_timeout():
    import time as _time

    import requests

    class Lento:
        modello = "x"
        timeout = 4.0
        tentativi = 1

        def __init__(self):
            self.timeout_usati = []

        def embed(self, t):
            self.timeout_usati.append(self.timeout)
            if self.timeout < 100:
                raise RuntimeError("non riuscito") from requests.ReadTimeout("Read timed out")
            return np.ones((1, 4), dtype=np.float32)

    lento = Lento()
    d = EmbedderDomande(lento, pausa_dopo_errore_s=60)
    with pytest.raises(Exception):
        d.vettore("q")
    d._riscaldamento.join(5)
    # il riscaldamento ha usato un timeout lungo e ha tolto la pausa: la domanda successiva riprova subito
    assert d._fermo_fino_a == 0.0 and d.ultimo_errore == ""
    with pytest.raises(Exception):
        d.vettore("q2")
    assert lento.timeout_usati[:3] == [4.0, 180.0, 4.0]  # riscaldamento con timeout lungo, originale invariato
    assert lento.timeout == 4.0


def test_motore_riscalda_senza_indice(tmp_path):
    c = sqlite3.connect(str(tmp_path / "n.db"))
    imp.ensure_schema(c)
    c.close()
    motore = MotoreRicercaNormattiva(tmp_path / "n.db")
    assert motore.riscalda(1.0) is False
