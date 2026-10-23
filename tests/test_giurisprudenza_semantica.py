import sqlite3

import pytest

from lex.ricerca_giuridica.embedding import EmbedderFinto
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from pct.giurisprudenza_semantica import cerca, costruisci, fondi


def sample(tmp_path):
    db = tmp_path / "corpus.db"
    corpus = GestioneCorpusGiurisprudenza(str(db))
    corpus.salva_sentenza(
        {
            "fonte": {"codice": "corte_cost", "nome": "Consulta", "tipo_fonte": "ufficiale"},
            "organo_giudicante": "Corte costituzionale",
            "numero_sentenza": "242",
            "anno_sentenza": 2019,
            "titolo": "Assistenza al suicidio",
            "esito": "Non punibile chi agevola la decisione autonoma.",
            "testo_integrale": "Fonte originale",
            "stato_verifica": "verificata",
            "massime": [{"testo": "Autodeterminazione nella scelta del trattamento sanitario", "ufficiale": True}],
        }
    )
    with sqlite3.connect(db) as c:
        row = c.execute("select id from sentenze").fetchone()[0]
        # Il test verifica unità ufficiali presenti, indipendentemente dal mapping del payload.
        c.execute("delete from massime")
        c.execute(
            "insert into massime(sentenza_id,testo,ufficiale) values(?,?,1)",
            (row, "Autodeterminazione nella scelta del trattamento sanitario"),
        )
    return db, corpus, row


def test_indice_ripresa_senza_ricalcolo_e_corpus_intatto(tmp_path):
    db, _corpus, sid = sample(tmp_path)
    before = db.read_bytes()
    engine = EmbedderFinto()
    a = costruisci(db, embedder=engine)
    b = costruisci(db, embedder=engine)
    assert a["nuovi"] >= 2 and b["nuovi"] == 0 and b["ricalcolati"] == 0
    assert db.read_bytes() == before
    assert cerca(db, "trattamento sanitario", embedder=engine)[0][0] == sid


def test_non_recupera_unita_modificate_o_cancellate(tmp_path):
    db, _corpus, _sid = sample(tmp_path)
    engine = EmbedderFinto()
    costruisci(db, embedder=engine)
    with sqlite3.connect(db) as c:
        c.execute("update massime set testo='Testo cambiato'")
        c.execute("update sentenze set esito='Dispositivo cambiato'")
    assert cerca(db, "trattamento sanitario", embedder=engine) == []
    costruisci(db, embedder=engine)
    with sqlite3.connect(db) as c:
        c.execute("delete from massime")
        c.execute("delete from sentenze")
    assert cerca(db, "trattamento sanitario", embedder=engine) == []


def test_ibrido_rispetta_filtri_ed_estremi(tmp_path):
    db, corpus, sid = sample(tmp_path)
    engine = EmbedderFinto()
    costruisci(db, embedder=engine)
    rows = corpus.cerca_sentenze_ibrida(q="Corte costituzionale 242/2019", embedder=engine)
    assert rows[0]["id"] == sid
    assert (
        corpus.cerca_sentenze_ibrida(q="trattamento sanitario", organo_giudicante="Cassazione", embedder=engine) == []
    )
    assert corpus.cerca_sentenze_ibrida(q="trattamento sanitario", solo_con_pdf=True, embedder=engine) == []


def test_modello_diverso_rifiutato_e_rrf_deduplica(tmp_path):
    db, _corpus, _sid = sample(tmp_path)
    costruisci(db, embedder=EmbedderFinto())
    with pytest.raises(ValueError):
        cerca(db, "sanitario", embedder=EmbedderFinto(dimensioni=128))
    assert fondi([1, 2], [2, 2, 3], limit=3) == [2, 1, 3]


def test_default_non_attiva_nuovo_motore(tmp_path, monkeypatch):
    _db, corpus, sid = sample(tmp_path)
    monkeypatch.delenv("LEX_GIURISPRUDENZA_SEMANTICA", raising=False)
    monkeypatch.setattr("pct.giurisprudenza_semantica.cerca", lambda *a, **k: pytest.fail("non attivo"))
    assert corpus.cerca_sentenze(q="Corte costituzionale 242/2019")[0]["id"] == sid


def test_indice_altro_corpus_e_costruzione_parziale_non_usati(tmp_path):
    db, _corpus, _sid = sample(tmp_path)
    folder = tmp_path / "indice"
    costruisci(db, embedder=EmbedderFinto(), folder=folder, massimo=1)
    assert cerca(db, "sanitario", embedder=EmbedderFinto(), folder=folder) == []
    costruisci(db, embedder=EmbedderFinto(), folder=folder)
    other = tmp_path / "altro.db"
    other.write_bytes(db.read_bytes())
    with pytest.raises(ValueError, match="altro corpus"):
        cerca(other, "sanitario", embedder=EmbedderFinto(), folder=folder)


def test_cache_pubblica_rifiuta_corpus_misti_e_riusa_solo_testi_identici(tmp_path):
    from pct.giurisprudenza_semantica import CacheConsultaPubblica

    db, _corpus, _sid = sample(tmp_path)
    cache = tmp_path / "pubblica.sqlite"
    with pytest.raises(ValueError, match="non esclusivamente"):
        CacheConsultaPubblica(EmbedderFinto(), cache, db)
    assert not cache.exists()
    with sqlite3.connect(db) as c:
        c.execute("update fonti_giurisprudenza set codice='corte_costituzionale'")
        c.execute("update sentenze set fonte_ufficiale_confermata=1,ecli='ECLI:IT:COST:2019:242'")
    engine = EmbedderFinto()
    wrapper = CacheConsultaPubblica(engine, cache, db)
    a = wrapper.embed(["testo pubblico"])
    engine.embed = lambda texts: pytest.fail("vettore pubblico gia calcolato")
    assert (a == wrapper.embed(["testo pubblico"])).all()


def test_metadati_openga_esclusi_anche_se_hanno_massima_legacy(tmp_path):
    from pct.giurisprudenza_semantica import prepara

    db, _corpus, _sid = sample(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE fonti_giurisprudenza SET codice='openga'")
        conn.execute("UPDATE sentenze SET testo_integrale_presente=0,testo_integrale=''")
    side = prepara(db, tmp_path / "indice-contenuti")
    try:
        assert side.execute("SELECT count(*) FROM units").fetchone()[0] == 0
    finally:
        side.close()


def test_fusione_conserva_primi_lessicali_senza_escludere_novita_semantiche():
    from pct.giurisprudenza_semantica import preserva_lessicali

    ranking = list(range(100, 120)) + list(range(1, 11))
    result = preserva_lessicali(ranking, list(range(1, 11)), limit=10)
    assert set(range(1, 6)).issubset(result)
    assert result[0] == 100
    assert len(result) == len(set(result)) == 10
    assert preserva_lessicali([100, 1], [1], limit=1) == [100]
