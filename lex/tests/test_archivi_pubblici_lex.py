"""Lex interroga la prassi (AdE, INPS), la Gazzetta Ufficiale e i testi della giustizia amministrativa.

Archivi costruiti nel test con le API dei moduli che li alimentano; la ricerca li apre in sola lettura e non crea
file quando mancano.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from lex.contracts import LexRequest
from lex.retrieval import archivi_pubblici as ap
from lex.retrieval.sources.archivi_pubblici import GazzettaSource, GiustiziaAmministrativaSource, PrassiSource
from pct.gazzetta.archivio import ArchivioGazzetta
from pct.gazzetta.serie import PER_CODICE
from pct.giustizia_amministrativa_testi import ArchivioTestiGA
from pct.prassi.archivio import ArchivioPrassi, identificativo


def _prassi(percorso):
    a = ArchivioPrassi(percorso)
    a.aggiungi([{"ente": "INPS", "tipo": "Circolare", "numero": "45", "data": "2026-03-10",
                 "oggetto": "Congedo parentale: nuove istruzioni", "url": "https://www.inps.it/circolare-45"},
                {"ente": "Agenzia delle Entrate", "tipo": "Risoluzione", "numero": "12/E", "data": "2026-02-01",
                 "oggetto": "Cedolare secca sui negozi", "url": "https://www.agenziaentrate.gov.it/ris-12"}])
    a.salva_testo(identificativo("INPS", "Circolare", "45", "2026-03-10"), "Il congedo parentale spetta per nove mesi.")
    a.salva_testo(identificativo("Agenzia delle Entrate", "Risoluzione", "12/E", "2026-02-01"), "La cedolare secca si applica.")


def _gazzetta(percorso):
    a = ArchivioGazzetta(percorso)
    a.salva_fascicolo({"serie": "SG", "numero": "260", "data": "2026-11-09", "url_sommario": "u", "letto_il": "x"}, [
        {"id": "gu_" + "a" * 24, "serie": "SG", "numero_gu": "260", "data_gu": "2026-11-09", "rubrica": "",
         "emittente": "", "intestazione": "DECRETO LEGISLATIVO 30 ottobre 2026, n. 180", "tipo": "decreto legislativo",
         "numero_atto": "180", "data_atto": "2026-10-30", "descrizione": "Disposizioni in materia di mediazione civile",
         "codice_redazionale": "26G00222", "pagina": "1", "posizione": 0, "url": "https://www.gazzettaufficiale.it/atto/x",
         "url_sommario": PER_CODICE["SG"].url_sommario("2026-11-09", "260"), "acquisito_il": "x"}])


def _ga(percorso):
    a = ArchivioTestiGA(percorso)
    a.salva_provvisoria("003", 2021, "202101234", "202100567", "Il soccorso istruttorio non può sanare l'offerta.", "2021-05-03")


def test_ricerche_negli_archivi(tmp_path):
    _prassi(tmp_path / "prassi.sqlite")
    _gazzetta(tmp_path / "gu.sqlite")
    _ga(tmp_path / "ga.sqlite")
    righe = ap.cerca_prassi("congedo parentale", ente="inps", percorso=tmp_path / "prassi.sqlite")
    assert [r["numero"] for r in righe] == ["45"]
    assert ap.cerca_prassi("congedo parentale", ente="agenzia_entrate", percorso=tmp_path / "prassi.sqlite") == []
    assert ap.cerca_gazzetta("mediazione", percorso=tmp_path / "gu.sqlite")[0]["numero_atto"] == "180"
    assert ap.cerca_testi_ga("soccorso istruttorio", percorso=tmp_path / "ga.sqlite")
    per_estremi = ap.cerca_testi_ga("TAR Lazio n. 1234/2021", percorso=tmp_path / "ga.sqlite")
    assert per_estremi and "soccorso" in per_estremi[0]["brano"]


def test_archivio_assente_non_crea_file(tmp_path):
    assert ap.cerca_prassi("x", percorso=tmp_path / "manca.sqlite") == []
    assert ap.cerca_gazzetta("x", percorso=tmp_path / "manca2.sqlite") == []
    assert ap.cerca_testi_ga("x", percorso=tmp_path / "manca3.sqlite") == []
    assert not list(tmp_path.iterdir())


def test_adattatori_del_retrieval(tmp_path, monkeypatch):
    _prassi(tmp_path / "prassi.sqlite")
    _gazzetta(tmp_path / "gu.sqlite")
    _ga(tmp_path / "ga.sqlite")
    monkeypatch.setenv("PCT_PRASSI_DB", str(tmp_path / "prassi.sqlite"))
    monkeypatch.setenv("GAZZETTA_UFFICIALE_DB", str(tmp_path / "gu.sqlite"))
    monkeypatch.setenv("PCT_GA_TESTI_DB", str(tmp_path / "ga.sqlite"))

    def req(q):
        return LexRequest(tenant_id="t", user_id="u", session_id="s", query=q)

    prassi = PrassiSource().search(["congedo parentale"], req("Circolare INPS sul congedo parentale"), {})
    assert prassi[0].source_type == "prassi" and prassi[0].official_url == "https://www.inps.it/circolare-45"
    gu = GazzettaSource().search(["mediazione"], req("Gazzetta: mediazione"), {})
    assert urlsplit(gu[0].official_url).scheme == "https" and urlsplit(gu[0].official_url).hostname == "www.gazzettaufficiale.it"
    ga = GiustiziaAmministrativaSource().search(["x"], req("TAR Lazio n. 1234/2021"), {})
    assert ga and ga[0].source_type == "giurisprudenza" and "1234/2021" in ga[0].title


def test_la_mappa_aggiunge_gli_archivi(monkeypatch):
    from lex.retrieval.source_router import SourceRouter
    from lex.router import LexRouter

    monkeypatch.setenv("LEX_MAPPA_STRUMENTI", "1")

    def fonti(q):
        r = LexRequest(tenant_id="t", user_id="u", session_id="s", query=q)
        return [f.__class__.__name__ for f in SourceRouter().resolve(r, {}, LexRouter().resolve_workflow(r))]

    assert "PrassiSource" in fonti("Ci sono circolari INPS sul congedo parentale?")
    assert "GazzettaSource" in fonti("Che decreti legislativi sono usciti in Gazzetta Ufficiale questo mese?")
    assert "GiustiziaAmministrativaSource" in fonti("Giurisprudenza del Consiglio di Stato sul soccorso istruttorio")
    assert fonti("TAR Lazio n. 3456/2019")[0] == "GiustiziaAmministrativaSource"


def test_retrieval_archivi_pubblici_continua_se_un_archivio_non_risponde(monkeypatch):
    from types import SimpleNamespace
    from lex.retrieval.sources import archivi_pubblici as fonti

    def non_disponibile(*args, **kwargs):
        raise OSError("Archivio temporaneamente non disponibile")

    domanda = SimpleNamespace(query="Agenzia delle Entrate")
    for sorgente, metodo in (
        (fonti.PrassiSource(), "cerca_prassi"),
        (fonti.GazzettaSource(), "cerca_gazzetta"),
        (fonti.GiustiziaAmministrativaSource(), "cerca_testi_ga"),
    ):
        monkeypatch.setattr(fonti, metodo, non_disponibile)
        assert sorgente.search([], domanda, {}) == []
