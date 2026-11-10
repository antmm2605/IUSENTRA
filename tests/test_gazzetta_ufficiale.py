"""Gazzetta Ufficiale: lettura dei sommari ufficiali, archivio con filtri e paginazione, endpoint della pagina.

Le pagine di prova riproducono la struttura dei sommari ufficiali letti il 10/11/2026 su www.gazzettaufficiale.it
(Serie generale n. 261 del 09/11/2026, 1ª Serie speciale n. 44 del 04/11/2026, 5ª Serie speciale n. 128).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g
import pytest

from pct.gazzetta import tipi
from pct.gazzetta.acquisizione import esegui_giro
from pct.gazzetta.archivio import ArchivioGazzetta, Filtri
from pct.gazzetta.serie import PER_CODICE
from pct.gazzetta.sommario import Fascicolo, SommarioIllegibile, atti_del_sommario, fascicoli_in_elenco

SG = PER_CODICE["SG"]
S1 = PER_CODICE["S1"]


def _risultato(href: str, intestazione: str, descrizione: str, pagina: str = "1") -> str:
    return (
        f'<span class="risultato"><a href="{href}"><span class="data">{intestazione}</span></a>'
        f'<a href="{href}">{descrizione}<span class="riferimento"></span><span class="pagina">Pag. {pagina}</span></a></span>'
    )


def _sommario(intestazione: str, corpo: str) -> bytes:
    return (
        '<html><body><div id="elenco_hp"><div class="riga_t"><div class="colonna_ultima intestazione">'
        f"{intestazione}</div></div><h2>Sommario</h2>{corpo}</div></body></html>"
    ).encode("utf-8")


def _atto_sg(codice: str) -> str:
    return f"/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-11-09&atto.codiceRedazionale={codice}&elenco30giorni=false"


SOMMARIO_SG_261 = _sommario(
    'Serie Generale n. <span class="estremi">261</span> del <span class="estremi">9-11-2026</span>',
    '<span class="rubrica">LEGGI ED ALTRI ATTI NORMATIVI</span>'
    + _risultato(_atto_sg("26G00218"), "LEGGE 29 ottobre 2026, n. 201",
                 "Modifica al codice di cui al decreto legislativo 30 giugno 2003, n. 196, in materia di "
                 "pubblicita' delle sentenze di assoluzione o proscioglimento. (26G00218)")
    + '<span class="rubrica">DECRETI, DELIBERE E ORDINANZE MINISTERIALI</span>'
    + '<span class="emettitore">MINISTERO DELL\'ECONOMIA E DELLE FINANZE</span>'
    + _risultato(_atto_sg("26A05934"), "DECRETO 9 novembre 2026", "Rideterminazione temporanea dell'aliquota d'accisa. (26A05934)", "4")
    + '<span class="rubrica">ESTRATTI, SUNTI E COMUNICATI</span>'
    + '<span class="emettitore">AGENZIA ITALIANA DEL FARMACO</span>'
    + _risultato(_atto_sg("26A05900"), "COMUNICATO", "Autorizzazione all'immissione in commercio del medicinale per uso umano. (26A05900)", "20"),
)
SOMMARIO_SG_260 = _sommario(
    'Serie Generale n. <span class="estremi">260</span> del <span class="estremi">7-11-2026</span>',
    '<span class="rubrica">DECRETI PRESIDENZIALI</span>'
    + _risultato(_atto_sg("26A05807").replace("2026-11-09", "2026-11-07"), "DELIBERA DEL CONSIGLIO DEI MINISTRI 28 ottobre 2026",
                 "Proroga dello stato di emergenza per intervento all'estero. (26A05807)"),
)
SOMMARIO_S1_44 = _sommario(
    '1a Serie Speciale - Corte Costituzionale n. <span class="estremi">44</span> del <span class="estremi">4-11-2026</span>',
    '<span class="rubrica">SENTENZE ED ORDINANZE DELLA CORTE</span>'
    + _risultato("/atto/corte_costituzionale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-11-04&atto.codiceRedazionale=T-260179",
                 "n. 179 SENTENZA 21 settembre - 2 novembre 2026",
                 "Giudizio di legittimita' costituzionale in via incidentale. Edilizia e urbanistica.")
    + '<span class="rubrica">ATTI DI PROMOVIMENTO DEL GIUDIZIO DELLA CORTE</span>'
    + _risultato("/atto/corte_costituzionale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-11-04&atto.codiceRedazionale=26C00220",
                 "n. 181 ORDINANZA (Atto di promovimento) 17 settembre 2026",
                 "Ordinanza del 17 settembre 2026 del Consiglio di Stato. (26C00220)"),
)


def _elenco(percorso: str, fascicoli: list[tuple[str, str]]) -> bytes:
    righe = "".join(
        f'<a href="/gazzetta/{percorso}/caricaDettaglio?dataPubblicazioneGazzetta={data}&numeroGazzetta={numero}&elenco30giorni=true">n. {numero}</a>'
        for data, numero in fascicoli
    )
    return f"<html><body>{righe}<a href='/altro'>altro</a></body></html>".encode("utf-8")


class _Risposta:
    def __init__(self, corpo: bytes, stato: int = 200):
        self.content = corpo
        self.status_code = stato
        self.headers: dict[str, str] = {}


def _rete(pagine: dict[str, bytes], chiamate: list[str] | None = None):
    def request_get(url: str, **_kwargs):
        if chiamate is not None:
            chiamate.append(url)
        for chiave, corpo in pagine.items():
            if chiave in url:
                return _Risposta(corpo)
        return _Risposta(b"", 404)

    return request_get


def _pagine_complete() -> dict[str, bytes]:
    return {
        "30giorni/serie_generale": _elenco("serie_generale", [("2026-11-07", "260"), ("2026-11-09", "261")]),
        "30giorni/corte_costituzionale": _elenco("corte_costituzionale", [("2026-11-04", "44")]),
        "serie_generale/caricaDettaglio?dataPubblicazioneGazzetta=2026-11-09&numeroGazzetta=261": SOMMARIO_SG_261,
        "serie_generale/caricaDettaglio?dataPubblicazioneGazzetta=2026-11-07&numeroGazzetta=260": SOMMARIO_SG_260,
        "corte_costituzionale/caricaDettaglio?dataPubblicazioneGazzetta=2026-11-04&numeroGazzetta=44": SOMMARIO_S1_44,
    }


@pytest.fixture()
def archivio(tmp_path: Path) -> ArchivioGazzetta:
    archivio = ArchivioGazzetta(tmp_path / "gazzetta_ufficiale.sqlite")
    esegui_giro(archivio, request_get=_rete(_pagine_complete()), serie=(SG, S1), pausa=0,
                adesso=datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc))
    return archivio


# --- lettura delle pagine ufficiali ---

def test_elenco_dei_fascicoli_dal_piu_recente():
    fascicoli = fascicoli_in_elenco(SG, _elenco("serie_generale", [("2026-11-07", "260"), ("2026-11-09", "261"), ("2026-11-09", "261")]))
    assert fascicoli == [Fascicolo("SG", "261", "2026-11-09"), Fascicolo("SG", "260", "2026-11-07")]


def test_sommario_legge_atti_con_ente_sezione_e_collegamento_ufficiale():
    atti = atti_del_sommario(SG, Fascicolo("SG", "261", "2026-11-09"), SOMMARIO_SG_261, acquisito_il="x")
    legge, decreto, comunicato = atti
    assert legge["intestazione"] == "LEGGE 29 ottobre 2026, n. 201"
    assert (legge["tipo"], legge["numero_atto"], legge["data_atto"]) == ("legge", "201", "2026-10-29")
    assert legge["codice_redazionale"] == "26G00218"
    assert legge["descrizione"].endswith("assoluzione o proscioglimento.")  # codice tolto dalla descrizione
    assert legge["url"].startswith("https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?")
    assert legge["url_sommario"] == "https://www.gazzettaufficiale.it/gazzetta/serie_generale/caricaDettaglio?dataPubblicazioneGazzetta=2026-11-09&numeroGazzetta=261"
    assert (decreto["tipo"], decreto["emittente"], decreto["pagina"]) == ("dm", "MINISTERO DELL'ECONOMIA E DELLE FINANZE", "4")
    assert decreto["rubrica"] == "DECRETI, DELIBERE E ORDINANZE MINISTERIALI"
    assert comunicato["tipo"] == "comunicato" and comunicato["emittente"] == "AGENZIA ITALIANA DEL FARMACO"
    assert [a["posizione"] for a in atti] == [0, 1, 2]


def test_sommario_di_un_altro_fascicolo_e_rifiutato():
    with pytest.raises(SommarioIllegibile):
        atti_del_sommario(SG, Fascicolo("SG", "262", "2026-11-10"), SOMMARIO_SG_261, acquisito_il="x")
    with pytest.raises(SommarioIllegibile):
        atti_del_sommario(SG, Fascicolo("SG", "261", "2026-11-09"), b"<html><body>Manutenzione</body></html>", acquisito_il="x")


def test_collegamento_fuori_dal_sito_ufficiale_scartato():
    pagina = _sommario(
        'Serie Generale n. <span class="estremi">261</span> del <span class="estremi">9-11-2026</span>',
        _risultato("https://esempio.invalid/atto", "LEGGE 29 ottobre 2026, n. 201", "Testo. (26G00218)"),
    )
    assert atti_del_sommario(SG, Fascicolo("SG", "261", "2026-11-09"), pagina, acquisito_il="x") == []


@pytest.mark.parametrize(
    ("serie", "intestazione", "emittente", "atteso"),
    [
        ("SG", "DECRETO-LEGGE 10 settembre 2026, n. 157", "", "decreto_legge"),
        ("SG", "DECRETO LEGISLATIVO 3 ottobre 2026, n. 160", "", "decreto_legislativo"),
        ("SG", "DECRETO DEL PRESIDENTE DELLA REPUBBLICA 12 ottobre 2026, n. 150", "", "dpr"),
        ("SG", "DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI 3 ottobre 2026", "", "dpcm"),
        ("SG", "DECRETO 2 novembre 2026", "MINISTERO DELLA GIUSTIZIA", "dm"),
        ("SG", "DECRETO 2 novembre 2026", "AGENZIA DELLE DOGANE", "decreto_altro"),
        ("SG", "TESTO COORDINATO DEL DECRETO-LEGGE 10 settembre 2026, n. 157", "", "testo_coordinato"),
        ("SG", "ERRATA-CORRIGE", "", "rettifica"),
        ("SG", "LEGGE COSTITUZIONALE 1 marzo 2026, n. 1", "", "legge"),
        ("S1", "n. 178 ORDINANZA 5 - 29 ottobre 2026", "", "ordinanza_corte"),
        ("S1", "n. 3 RICORSO PER LEGITTIMITA' COSTITUZIONALE 2 ottobre 2026", "", "atto_promovimento"),
        ("S2", "REGOLAMENTO 4 giugno 2026 , n. 1221", "", "atto_ue"),
        ("S3", "LEGGE REGIONALE 10 febbraio 2026 , n. 4", "REGIONE LOMBARDIA", "legge_regionale"),
        ("S3", "DECRETO DEL PRESIDENTE DELLA PROVINCIA 20 febbraio 2026 , n. 2", "", "atto_regionale"),
        ("S4", "CONCORSO (scad. 6 dicembre 2026)", "MINISTERO DELLA SALUTE", "concorso"),
        ("S5", "", "COMUNE DI VIMODRONE", "contratto"),
    ],
)
def test_tipo_dell_atto_dall_intestazione_ufficiale(serie, intestazione, emittente, atteso):
    assert tipi.tipo_atto(serie, intestazione, emittente) == atteso


def test_data_e_numero_dell_atto():
    assert tipi.data_atto("n. 179 SENTENZA 21 settembre - 2 novembre 2026") == "2026-11-02"
    assert tipi.numero_atto("n. 179 SENTENZA 21 settembre - 2 novembre 2026") == "179"
    assert tipi.data_atto("CONCORSO (scad. 6 dicembre 2026)") == ""  # la scadenza non è la data dell'atto


# --- giro di lettura ---

def test_giro_archivia_e_non_rilegge_i_fascicoli_gia_letti(archivio: ArchivioGazzetta):
    chiamate: list[str] = []
    esito = esegui_giro(archivio, request_get=_rete(_pagine_complete(), chiamate), serie=(SG, S1), pausa=0)
    assert esito["fascicoli_nuovi"] == 0
    assert all("30giorni" in url for url in chiamate)  # solo i due elenchi
    stato = archivio.stato_serie()
    assert stato["SG"]["ultimo_fascicolo"]["numero"] == "261"
    assert stato["SG"]["atti"] == 4 and stato["S1"]["atti"] == 2


def test_serie_non_raggiungibile_registrata_senza_fermare_le_altre(tmp_path: Path):
    archivio = ArchivioGazzetta(tmp_path / "g.sqlite")
    pagine = _pagine_complete()
    del pagine["30giorni/corte_costituzionale"]
    esito = esegui_giro(archivio, request_get=_rete(pagine), serie=(SG, S1), pausa=0)
    assert esito["serie_non_raggiungibili"] == ["S1"]
    assert esito["esiti"]["SG"]["fascicoli_nuovi"] == 2
    stato = archivio.stato_serie()["S1"]
    assert not stato["ultimo_esito_ok"] and "404" in stato["messaggio"]


def test_sommario_illeggibile_resta_da_leggere(tmp_path: Path):
    archivio = ArchivioGazzetta(tmp_path / "g.sqlite")
    pagine = _pagine_complete()
    pagine["serie_generale/caricaDettaglio?dataPubblicazioneGazzetta=2026-11-07&numeroGazzetta=260"] = b"<html>vuota</html>"
    esito = esegui_giro(archivio, request_get=_rete(pagine), serie=(SG,), pausa=0)
    assert esito["esiti"]["SG"]["fascicoli_nuovi"] == 1
    assert not esito["esiti"]["SG"]["ok"] and "07/11/2026" in esito["esiti"]["SG"]["messaggio"]
    assert archivio.fascicoli_letti("SG") == {"SG|2026-11-09|261"}


def test_tempo_esaurito_prima_il_fascicolo_piu_recente_di_ogni_serie(tmp_path: Path):
    archivio = ArchivioGazzetta(tmp_path / "g.sqlite")
    esito = esegui_giro(archivio, request_get=_rete(_pagine_complete()), serie=(SG, S1), pausa=0, tempo_massimo=0)
    assert esito["fascicoli_nuovi"] == 0
    assert "ancora da leggere" in esito["esiti"]["SG"]["messaggio"]


# --- archivio: ricerca, filtri, paginazione ---

def test_ricerca_filtri_e_conteggi(archivio: ArchivioGazzetta):
    tutti = archivio.cerca(Filtri())
    assert tutti["totale"] == 6 and tutti["in_archivio"] == 6
    assert [a["data_gu"] for a in tutti["atti"]] == sorted((a["data_gu"] for a in tutti["atti"]), reverse=True)
    assert tutti["atti"][0]["intestazione"] == "LEGGE 29 ottobre 2026, n. 201"  # ordine del sommario a parità di data
    assert archivio.cerca(Filtri(q="PROSCIOGLIMENTO assoluzione"))["totale"] == 1
    assert archivio.cerca(Filtri(q="26A05934"))["atti"][0]["tipo"] == "dm"
    solo_corte = archivio.cerca(Filtri(serie=("S1",)))
    assert solo_corte["totale"] == 2
    assert solo_corte["conteggi"]["serie"] == {"SG": 4, "S1": 2}  # i conteggi della serie ignorano il filtro serie
    assert archivio.cerca(Filtri(tipo=("legge", "dm")))["totale"] == 2
    assert archivio.cerca(Filtri(emittente="AGENZIA ITALIANA DEL FARMACO"))["totale"] == 1
    assert archivio.cerca(Filtri(dal="2026-11-05", al="2026-11-08"))["totale"] == 1
    assert archivio.cerca(Filtri(numero_gu="44"))["totale"] == 2
    assert archivio.cerca(Filtri(rubrica="DECRETI PRESIDENZIALI"))["totale"] == 1
    assert archivio.cerca(Filtri(ordine="meno_recenti"))["atti"][0]["data_gu"] == "2026-11-04"


def test_paginazione_lato_server(archivio: ArchivioGazzetta):
    prima = archivio.cerca(Filtri(per_pagina=5, pagina=1))
    seconda = archivio.cerca(Filtri(per_pagina=5, pagina=2))
    assert len(prima["atti"]) == 5 and len(seconda["atti"]) == 1
    assert not {a["id"] for a in prima["atti"]} & {a["id"] for a in seconda["atti"]}


def test_enti_piu_frequenti(archivio: ArchivioGazzetta):
    assert ("AGENZIA ITALIANA DEL FARMACO", 1) in archivio.enti(Filtri())


def test_fascicolo_riletto_sostituisce_gli_atti(archivio: ArchivioGazzetta):
    atti = atti_del_sommario(SG, Fascicolo("SG", "261", "2026-11-09"), SOMMARIO_SG_261, acquisito_il="y")[:1]
    archivio.salva_fascicolo({"serie": "SG", "numero": "261", "data": "2026-11-09", "url_sommario": "u", "letto_il": "y"}, atti)
    assert archivio.cerca(Filtri(numero_gu="261"))["totale"] == 1


# --- endpoint della pagina e della Panoramica ---

def _client(tmp_path: Path, *, autenticato: bool = True, db: Path | None = None):
    from web.blueprints.api_v1_gazzetta import api_v1_gazzetta

    app = Flask(__name__)
    app.config.update(TESTING=True, GAZZETTA_UFFICIALE_DB=str(db or tmp_path / "assente.sqlite"))

    @app.before_request
    def _utente():
        if autenticato:
            g.utente_corrente = SimpleNamespace(id="u1", ruolo="avvocato")

    app.register_blueprint(api_v1_gazzetta)
    return app.test_client()


def test_endpoint_richiede_autenticazione(tmp_path: Path):
    assert _client(tmp_path, autenticato=False).get("/api/v1/ui/gazzetta-ufficiale").status_code == 401


def test_endpoint_archivio_assente_lo_dice_in_chiaro(tmp_path: Path):
    dati = _client(tmp_path).get("/api/v1/ui/gazzetta-ufficiale").get_json()
    assert dati["ok"] and dati["archiveMissing"] and dati["items"] == []
    assert "non è ancora stato creato" in dati["message"]
    assert [s["id"] for s in dati["sourceStates"]] == ["SG", "S1", "S2", "S3", "S4", "S5"]


def test_endpoint_filtri_paginazione_e_voce(tmp_path: Path, archivio: ArchivioGazzetta):
    client = _client(tmp_path, db=archivio.percorso)
    dati = client.get("/api/v1/ui/gazzetta-ufficiale?serie=SG&tipo=legge,dm&per_pagina=5&q=").get_json()
    assert dati["total"] == 2 and not dati["hasMore"]
    legge = dati["items"][0]
    assert legge["title"] == "LEGGE 29 ottobre 2026, n. 201"
    assert legge["seriesLabel"] == "Serie generale" and legge["issueNumber"] == "261" and legge["issueDate"] == "2026-11-09"
    assert legge["kindLabel"] == "Legge" and legge["officialUrl"].startswith("https://www.gazzettaufficiale.it/")
    assert {k["id"] for k in dati["facets"]["kinds"]} >= {"legge", "dm", "comunicato"}
    pagina = client.get("/api/v1/ui/gazzetta-ufficiale?per_pagina=5&pagina=2").get_json()
    assert pagina["page"] == 2 and len(pagina["items"]) == 1
    date = client.get("/api/v1/ui/gazzetta-ufficiale?dal=2026-11-08&al=2026-11-01").get_json()  # date invertite
    assert date["total"] == 3  # S1 n. 44 del 04/11 e SG n. 260 del 07/11
    sbagliati = client.get("/api/v1/ui/gazzetta-ufficiale?serie=XX&tipo=nessuno&dal=31/12/2026&per_pagina=9999").get_json()
    assert sbagliati["total"] == 6 and sbagliati["pageSize"] == 100


def test_endpoint_ultime_cinque_per_la_panoramica(tmp_path: Path, archivio: ArchivioGazzetta):
    dati = _client(tmp_path, db=archivio.percorso).get("/api/v1/ui/gazzetta-ufficiale/ultime").get_json()
    assert len(dati["items"]) == 5
    assert dati["items"][0]["title"] == "LEGGE 29 ottobre 2026, n. 201"
    assert {voce["series"] for voce in dati["items"]} <= {"SG", "S1"}


def test_aggiorna_ora_non_piu_di_una_volta_ogni_cinque_minuti(tmp_path: Path, archivio: ArchivioGazzetta):
    from web.services.gazzetta_runtime import aggiorna_ora

    chiamate: list[dict] = []
    config = {"GAZZETTA_UFFICIALE_DB": str(archivio.percorso)}
    subito = aggiorna_ora(config, adesso=datetime(2026, 11, 10, 9, 3, tzinfo=timezone.utc), esegui=lambda c, **k: chiamate.append(k))
    assert not subito["eseguito"] and not chiamate
    dopo = aggiorna_ora(config, adesso=datetime(2026, 11, 10, 9, 6, tzinfo=timezone.utc), esegui=lambda c, **k: chiamate.append(k) or {})
    assert dopo["eseguito"] and chiamate == [{"tempo_massimo": 45}]


# --- pagina React registrata nella shell ---

def test_pagina_gazzetta_e_solo_react(monkeypatch):
    from flask import jsonify

    from web.blueprints import react_shell
    from web.bootstrap import react_route_gate as gate

    percorso = "/ricerca-legale/gazzetta-ufficiale"
    assert gate._is_react_route(percorso) and not gate._excluded(percorso)
    assert react_shell._route_component_key(percorso) == "src/components/GazzettaUfficialePage.tsx"
    app = Flask(__name__)
    app.secret_key = "fixture-gazzetta"
    with app.test_request_context(percorso):
        assert react_shell._deve_mantenere_vista_classica() is False

    @app.before_request
    def _utente():
        g.utente_corrente = SimpleNamespace(must_change_password=False)

    monkeypatch.setattr(gate, "render_react_shell_response", lambda path, **kw: jsonify(shell="react", percorso=path))
    gate.register_react_route_gate(app)
    with app.test_client() as client:
        for query in ("", "?_legacy=1", "?serie=SG&tipo=legge"):
            risposta = client.get(percorso + query, headers={"Accept": "text/html"})
            assert risposta.status_code == 200 and risposta.get_json()["shell"] == "react"


def test_a_parita_di_data_prima_la_serie_generale(tmp_path: Path):
    archivio = ArchivioGazzetta(tmp_path / "g.sqlite")
    base = {"rubrica": "", "emittente": "", "numero_atto": "", "data_atto": "", "descrizione": "x", "codice_redazionale": "",
            "pagina": "", "url": "https://www.gazzettaufficiale.it/a", "url_sommario": "u", "acquisito_il": "x"}
    for serie, numero in (("S2", "88"), ("SG", "261"), ("S5", "128")):
        archivio.salva_fascicolo(
            {"serie": serie, "numero": numero, "data": "2026-11-09", "url_sommario": "u", "letto_il": "x"},
            [{**base, "id": f"id-{serie}", "serie": serie, "numero_gu": numero, "data_gu": "2026-11-09",
              "intestazione": serie, "tipo": "altro", "posizione": 0}],
        )
    assert [a["serie"] for a in archivio.cerca(Filtri())["atti"]] == ["SG", "S2", "S5"]
