from concurrent.futures import ThreadPoolExecutor
from datetime import date

from lex.normativa.biblioteca.acquisizione import acquisisci
from lex.normativa.biblioteca.lettura import leggi_articoli
from lex.normativa.biblioteca.recupero import recupera
from lex.normativa.consultazione import importa_fonti
from pct.legal_update_job_queue import LegalUpdateJobQueue
import json


def fixture_package(tmp_path):
    folder=tmp_path/"iniziale"/"atti";folder.mkdir(parents=True)
    row={"atto":"Fixture", "chiave":"legge_81_2017", "articolo":"18", "testo":"Testo iniziale non giuridico.",
         "urn":"urn:nir:stato:legge:2017-05-22;81", "titolo_atto":"Fixture", "data_atto":"2017-05-22",
         "url":"https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2017-05-22;81"}
    (folder/"fixture.jsonl").write_text(json.dumps(row))
    db=tmp_path/"codici_leggi.sqlite";importa_fonti(folder.parent,db,"2025-01-01")
    return db,row


def test_recovers_requested_edition_and_reuses_full_text(tmp_path):
    db,row=fixture_package(tmp_path);calls=[]
    def importer(db,cache,**kw):
        calls.append(kw)
        return acquisisci(db,cache,scarica_normattiva=lambda *_:[dict(row,testo="Testo della versione richiesta.",
            consolidato_al=kw["versione_al"].isoformat(),raccolto_il=date.today().isoformat())],**kw)
    ref={"chiave":"legge_81_2017","articolo":"18"}
    for _ in range(2):
        result=recupera(db,[ref],data_riferimento=date(2026,10,25),cartella=tmp_path/"recuperi",acquisitore=importer)
        assert result["esiti"][0]["lettura"]["articoli"][0]["testo"]=="Testo della versione richiesta."
    assert len(calls)==1
    old=leggi_articoli(db,[dict(ref,edizione="2025-01-01")])
    assert old["articoli"][0]["testo"]=="Testo iniziale non giuridico."


def test_unknown_type_never_guessed_and_no_network(tmp_path):
    db,_=fixture_package(tmp_path)
    def forbidden(*a,**k):raise AssertionError("Acquisizione inattesa")
    result=recupera(db,[{"chiave":"81/2017","articolo":"22"}],data_riferimento=date(2026,10,25),cartella=tmp_path/"q",acquisitore=forbidden)
    assert result["esiti"][0]["stato"]=="identita_non_deducibile"


def test_claim_only_requested_job_is_atomic(tmp_path):
    queue=LegalUpdateJobQueue(tmp_path/"queue.sqlite")
    a=queue.enqueue(source_code="altro",dedupe_key="altro")
    b=queue.enqueue(source_code="normativa",dedupe_key="normativa")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:queue.claim(b.job_id),range(2)))
    assert sum(x is not None for x in results)==1
    assert queue.get(a.job_id).status=="queued"
    assert queue.get(b.job_id).attempts==1
