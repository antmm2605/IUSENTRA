"""Lavori orari dei testi della Giustizia amministrativa e della prassi: l'app è l'unico scrittore degli archivi."""
import sqlite3
from types import SimpleNamespace

from pct.fonti_in_sfondo import (
    catalogo_openga,
    giro_prassi,
    giro_testi_ga,
    percorso_ga,
    percorso_prassi,
    tempo_giro,
    uffici_dei_fascicoli,
)
from pct.giustizia_amministrativa_testi import ArchivioTestiGA
from pct.scheduler_corsie import CORSIA_FONTI_PUBBLICHE, corsia_del_lavoro, esecutori

PAGINA = ("<p>Pubblicato il 11/03/2026</p><p>REPUBBLICA ITALIANA</p><p>Il Consiglio di Stato ... " + "motivazione " * 40
          + "</p>").encode()


def _config(tmp_path, **altro):
    return {"LEGAL_INTELLIGENCE_DB": str(tmp_path / "data" / "intelligence" / "motori.json"), **altro}


def test_archivi_accanto_agli_archivi_delle_fonti_e_tempo_del_giro(tmp_path):
    config = _config(tmp_path)
    assert percorso_ga(config) == tmp_path / "data" / "intelligence" / "ga_testi.sqlite"
    assert percorso_prassi(config) == tmp_path / "data" / "intelligence" / "prassi.sqlite"
    assert tempo_giro({}, "PCT_GA_TEMPO_GIRO") == 1200
    assert tempo_giro({"PCT_GA_TEMPO_GIRO": "9999"}, "PCT_GA_TEMPO_GIRO") == 3300
    assert tempo_giro({"PCT_PRASSI_TEMPO_GIRO": "600"}, "PCT_PRASSI_TEMPO_GIRO") == 600
    assert tempo_giro({"PCT_PRASSI_TEMPO_GIRO": "x"}, "PCT_PRASSI_TEMPO_GIRO") == 1200
    assert catalogo_openga({"OPENGA_CATALOGO_DB": str(tmp_path / "assente.db")}) is None


def _studio(tmp_path, nome, uffici):
    cartella = tmp_path / "data" / "tenants" / nome
    cartella.mkdir(parents=True)
    with sqlite3.connect(cartella / "studio.db") as conn:
        conn.execute("CREATE TABLE fascicoli (id TEXT, tribunale TEXT)")
        conn.executemany("INSERT INTO fascicoli VALUES (?, ?)", [(str(i), u) for i, u in enumerate(uffici)])


def test_giro_ga_catalogo_sedi_dei_fascicoli_e_ripresa(tmp_path):
    _studio(tmp_path, "studio-a", ["Tar venezia", "Tribunale di Taranto", ""])
    catalogo = tmp_path / "catalogo.db"
    with sqlite3.connect(catalogo) as conn:
        conn.execute("CREATE TABLE righe (sede TEXT, nome_sede TEXT, tipo TEXT, numero TEXT, anno INTEGER, ricorso TEXT, "
                     "oggetto TEXT, esito_originale TEXT)")
        conn.executemany("INSERT INTO righe VALUES (?,?,?,?,?,?,?,?)", [
            ("002", "CdS GIURISDIZIONALE - ROMA", "SENTENZA", "202600070", 2026, "202500001", "APPALTI", ""),
            ("030", "TAR VENETO - VENEZIA", "SENTENZA", "202600020", 2026, "202500002", "EDILIZIA", ""),
            ("002", "CdS GIURISDIZIONALE - ROMA", "ORDINANZA", "202600071", 2026, "202500003", "", ""),
        ])
    config = _config(tmp_path, OPENGA_CATALOGO_DB=str(catalogo), PCT_GA_TEMPO_GIRO="60")
    assert uffici_dei_fascicoli(config) == ["Tar venezia", "Tribunale di Taranto"]
    letti = []

    def scarica(url):
        letti.append(url)
        return SimpleNamespace(status_code=200, url=url, content=PAGINA)

    esito = giro_testi_ga(config, scarica=scarica, dormi=lambda _s: None)
    assert esito["estremi_nuovi"] == 2 and esito["sedi_studio"] == ["030"] and esito["letti"] == 2
    assert "schema=cds" in letti[0] and "schema=tar_ve" in letti[1]
    # Giro successivo: catalogo invariato (non si ricarica), coda vuota.
    di_nuovo = giro_testi_ga(config, scarica=scarica, dormi=lambda _s: None)
    assert "estremi_nuovi" not in di_nuovo and di_nuovo["letti"] == 0 and di_nuovo["stati"] == {"letto": 2}
    assert ArchivioTestiGA(percorso_ga(config)).sedi_studio() == {"030"}


def test_giro_prassi_nello_stesso_archivio_dell_app(tmp_path, monkeypatch):
    chiamate = {}

    def tratto(archivio, scarica, *, tempo_massimo, pausa):
        chiamate.update(percorso=archivio.percorso, tempo=tempo_massimo)
        return {"testi_nuovi": 0, "elenchi": {}}

    monkeypatch.setattr("pct.prassi.recupero.esegui_tratto", tratto)
    config = _config(tmp_path, PCT_PRASSI_TEMPO_GIRO="900")
    assert giro_prassi(config, scarica=lambda url: None) == {"testi_nuovi": 0, "elenchi": {}}
    assert str(chiamate["percorso"]).endswith("intelligence/prassi.sqlite") and chiamate["tempo"] == 900


def test_corsia_propria_per_i_due_lavori():
    assert corsia_del_lavoro("giustizia_amministrativa_testi") == CORSIA_FONTI_PUBBLICHE
    assert corsia_del_lavoro("prassi_agenzia_entrate_inps") == CORSIA_FONTI_PUBBLICHE
    assert corsia_del_lavoro("manual_prassi_agenzia_entrate_inps_12") == CORSIA_FONTI_PUBBLICHE
    assert CORSIA_FONTI_PUBBLICHE in esecutori()
