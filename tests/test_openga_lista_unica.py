import numpy as np

from lex.ricerca_giuridica.indice_vettoriale import IndiceVettoriale
from pct.openga_query import sede_richiesta


def test_sede_esplicita_non_e_giudice_citato():
    sedi={"MI":"TAR LOMBARDIA - MILANO","TO":"TAR PIEMONTE - TORINO","RM":"TAR LAZIO - ROMA"}
    assert sede_richiesta("al TAR milanese esecuzione sentenza tribunale Torino",sedi)==["MI"]
    assert sede_richiesta("tribunale milanese del lavoro",sedi)==[]
    assert sede_richiesta("ricorsi al TAR romano per riconoscimento",sedi)==["RM"]
    assert sede_richiesta("controversia torinese",sedi)==[]


def test_regione_con_due_sedi_non_viene_scelta_arbitrariamente():
    sedi={"AQ":"TAR ABRUZZO - L'AQUILA","PE":"TAR ABRUZZO - PESCARA"}
    assert sede_richiesta("al TAR abruzzese",sedi)==["AQ","PE"]
    assert sede_richiesta("al TAR Abruzzo",sedi)==["AQ","PE"]
    assert sede_richiesta("al TAR dell'Aquila",sedi)==["AQ"]


def test_aggettivi_regionali_derivati_non_sinonimi_tematici():
    sedi={"FI":"TAR TOSCANA - FIRENZE","PG":"TAR UMBRIA - PERUGIA","SA":"TAR CAMPANIA - SALERNO"}
    assert sede_richiesta("al TAR toscano",sedi)==["FI"]
    assert sede_richiesta("al TAR umbro",sedi)==["PG"]
    assert sede_richiesta("al TAR salernitano",sedi)==["SA"]


def test_filtro_prima_del_topk_anche_per_vicino_globalmente_lontano(tmp_path,monkeypatch):
    monkeypatch.setattr("lex.ricerca_giuridica.costruzione_iniziale.disponibile",lambda meta:True)
    engine=IndiceVettoriale(tmp_path,{"righe":4,"dimensioni":2})
    engine._mappe={"righe":4,"vettori":np.array([[9,0],[8,0],[7,0],[1,1]],dtype=np.int8),"scale":np.ones(4),"ids":np.array([10,11,12,13])}
    query=np.array([[1.,0.]],dtype=np.float32)
    assert engine.cerca(query,k=1)[0][0]==10
    assert engine.cerca(query,k=1,ids_ammessi={13})[0][0]==13
    assert engine.cerca(query,k=1,ids_ammessi=set())==[]
    assert engine.cerca(query,k=1,ids_ammessi={99})==[]
    assert engine.cerca(query,k=1,ids_ammessi={10,11,12,13})==engine.cerca(query,k=1)


def test_topk_filtrato_corrisponde_al_calcolo_completo_su_blocchi(tmp_path,monkeypatch):
    monkeypatch.setattr("lex.ricerca_giuridica.costruzione_iniziale.disponibile",lambda meta:True)
    rng=np.random.default_rng(42)
    vectors=rng.integers(-120,120,size=(31,8),dtype=np.int8)
    scales=rng.random(31).astype(np.float32)
    ids=np.arange(100,131,dtype=np.int64)
    engine=IndiceVettoriale(tmp_path,{"righe":31,"dimensioni":8})
    engine._mappe={"righe":31,"vettori":vectors,"scale":scales,"ids":ids}
    query=rng.random((1,8)).astype(np.float32)
    scores=(vectors.astype(np.float32) @ (query[0]/np.linalg.norm(query[0]))) * scales
    allowed={102,105,117,124,129}
    expected=[int(ids[i]) for i in np.argsort(-scores) if int(ids[i]) in allowed][:3]
    assert [row[0] for row in engine.cerca(query,k=3,blocco=4,ids_ammessi=allowed)]==expected


def test_varianti_duplicate_non_moltiplicano_il_consenso(tmp_path,monkeypatch):
    import sqlite3

    from pct.openga_catalogo import CatalogoOpenGA
    db=tmp_path/"catalog.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE attive(sede TEXT,nome_sede TEXT)")
    def row(name):
        return {"relazione_id":name,"oggetto":"descrizione " + name,"esito":"esito"}
    lex=[row("a"),row("b"),row("c"),row("d")]
    semantic=[row("z")]
    catalog=CatalogoOpenGA(db)
    def search(query,**kwargs):
        if kwargs.get("semantica"):
            return semantic
        return lex if query=="domanda" else []
    monkeypatch.setattr(catalog,"cerca",search)
    first=catalog.cerca_fusa("domanda",traccia=True)
    expanded=catalog.cerca_fusa("domanda",traccia=True,riformulatore=lambda q:{"queries":["variante prima","variante seconda"]})
    assert [r["relazione_id"] for r in first["risultati"]]==["a","b","c","d","z"]
    assert expanded["risultati"]==first["risultati"]


def test_indice_assente_non_dichiara_ricerca_semantica_riuscita(tmp_path):
    from pct.openga_catalogo import CatalogoOpenGA
    catalog=CatalogoOpenGA(tmp_path/"catalog.db")
    connection=catalog._connect()
    connection.close()
    result=catalog.cerca_fusa("domanda di prova")
    assert result["risultati"]==[]
    assert "assente" in result["errore_semantico"]
    assert not (tmp_path/"catalog.db.vettori-oggetti").exists()


def test_guasto_semantico_conserva_tutta_la_lista_non_solo_tre(tmp_path,monkeypatch):
    import sqlite3

    from pct.openga_catalogo import CatalogoOpenGA
    db=tmp_path/"catalog.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE attive(sede TEXT,nome_sede TEXT)")
    rows=[{"relazione_id":str(i),"oggetto":"oggetto "+str(i),"esito":"esito"} for i in range(8)]
    catalog=CatalogoOpenGA(db)
    def search(q,**kw):
        if kw.get("semantica"):
            raise RuntimeError("embedding indisponibile")
        return rows if q=="controversia esempio" else list(reversed(rows))
    monkeypatch.setattr(catalog,"cerca",search)
    calls=[]
    def forbidden(*args):
        calls.append(True)
        raise AssertionError("non deve essere chiamato")
    result=catalog.cerca_fusa("controversia esempio",reranker=forbidden)
    assert result["risultati"]==rows
    assert result["errore_semantico"] and not calls


def test_pool_candidati_varia_solo_il_riordino_non_recupero(tmp_path, monkeypatch):
    import sqlite3

    import pytest

    from pct.openga_catalogo import CatalogoOpenGA
    db = tmp_path / "catalog.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE attive(sede TEXT,nome_sede TEXT)")
    rows = [{"relazione_id": str(i), "oggetto": "descrizione " + str(i), "esito": "esito"} for i in range(120)]
    catalog = CatalogoOpenGA(db)
    monkeypatch.setattr(catalog, "cerca", lambda q, **kw: rows[:kw["limit"]])
    seen = []
    def rank(query, candidates):
        seen.append(len(candidates))
        return list(range(len(candidates)))
    for pool in (30, 40, 100):
        result = catalog.cerca_fusa("controversia", reranker=rank, rerank_candidates=pool)
        assert seen[-1] == pool
        assert result["risultati"][:3] == rows[:3]
        assert len(result["risultati"]) == 10 and result["errore_reranker"] is None
    catalog.cerca_fusa("controversia", reranker=rank)
    assert seen[-1] == 100
    for invalid in (True, "40", 40.0, 0, 29, 101):
        with pytest.raises(ValueError, match="Pool"):
            catalog.cerca_fusa("controversia", rerank_candidates=invalid)
