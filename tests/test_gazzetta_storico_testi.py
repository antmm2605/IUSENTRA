"""Gazzetta Ufficiale: archivio dal 01/01/2022 con il testo degli atti, ricerca per pertinenza e accenti univoci."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from pct.gazzetta import storico
from pct.gazzetta.accenti import accenta
from pct.gazzetta.archivio import ArchivioGazzetta, Filtri, espressione_fts
from pct.gazzetta.serie import PER_CODICE
from pct.gazzetta.testo_atto import leggi_testo

SG = PER_CODICE["SG"]
ADESSO = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _atto(identificativo: str, data: str, intestazione: str, descrizione: str, *, numero: str = "1", posizione: int = 0):
    return {
        "id": identificativo, "serie": "SG", "numero_gu": numero, "data_gu": data, "rubrica": "LEGGI ED ALTRI ATTI NORMATIVI",
        "emittente": "", "intestazione": intestazione, "tipo": "decreto_legislativo", "numero_atto": "", "data_atto": "",
        "descrizione": descrizione, "codice_redazionale": "", "pagina": "1", "posizione": posizione,
        "url": f"https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta={data}&atto.codiceRedazionale=X{identificativo[-3:]}",
        "url_sommario": SG.url_sommario(data, numero), "acquisito_il": "2026-11-21T12:00:00Z",
    }


def _archivio(tmp_path) -> ArchivioGazzetta:
    archivio = ArchivioGazzetta(tmp_path / "gu.sqlite")
    archivio.salva_fascicolo(
        {"serie": "SG", "numero": "243", "data": "2022-10-17", "url_sommario": SG.url_sommario("2022-10-17", "243"), "letto_il": "x"},
        [_atto("gu_" + "a" * 24, "2022-10-17", "DECRETO LEGISLATIVO 10 ottobre 2022, n. 149",
               "Attuazione della legge 26 novembre 2021, n. 206, recante delega al Governo per l'efficienza del processo "
               "civile e per la revisione della disciplina degli strumenti di risoluzione alternativa delle controversie.",
               numero="243")])
    archivio.salva_fascicolo(
        {"serie": "SG", "numero": "10", "data": "2023-01-13", "url_sommario": SG.url_sommario("2023-01-13", "10"), "letto_il": "x"},
        [_atto("gu_" + "b" * 24, "2023-01-13", "CORTE SUPREMA DI CASSAZIONE",
               "Sentenza sul processo penale: rinvio pregiudiziale. Tribunale civile non competente.", numero="10"),
         _atto("gu_" + "c" * 24, "2023-01-13", "DECRETO 5 gennaio 2023",
               "Regole tecniche per il processo civile telematico.", numero="10", posizione=1),
         _atto("gu_" + "d" * 24, "2023-01-13", "DECRETO 6 gennaio 2023", "Contributi alle imprese agricole.",
               numero="10", posizione=2)])
    return archivio


def test_processo_civile_trova_prima_gli_atti_sul_processo_civile(tmp_path):
    archivio = _archivio(tmp_path)
    risultato = archivio.cerca(Filtri(q="processo civile", ordine="pertinenza"))
    ordine = [atto["id"][3] for atto in risultato["atti"]]
    assert risultato["totale"] == 3, ordine  # anche la sentenza (contiene entrambe le parole), ma per ultima
    assert ordine[-1] == "b" and set(ordine[:2]) == {"a", "c"}
    # La frase fra virgolette è esatta: la sentenza («processo penale … civile») non c'è.
    frase = archivio.cerca(Filtri(q='"processo civile"', ordine="pertinenza"))
    assert sorted(a["id"][3] for a in frase["atti"]) == ["a", "c"]
    # «civili»/«processi»: le desinenze si trovano lo stesso.
    assert archivio.cerca(Filtri(q="processi civili"))["totale"] == 3
    assert espressione_fts("il processo civile") == ("process* AND civil*", "NEAR(process* civil*, 3)")


def test_l_archivio_conserva_dal_2022_e_non_scorre(tmp_path):
    archivio = _archivio(tmp_path)
    archivio.salva_fascicolo(
        {"serie": "SG", "numero": "300", "data": "2021-12-31", "url_sommario": SG.url_sommario("2021-12-31", "300"), "letto_il": "x"},
        [_atto("gu_" + "e" * 24, "2021-12-31", "DECRETO 30 dicembre 2021", "Atto del 2021.", numero="300")])
    archivio.pota(oggi=date(2026, 11, 21))
    rimasti = {a["data_gu"] for a in archivio.cerca(Filtri(per_pagina=50))["atti"]}
    # Il 2021 fuori dall'archivio; il 2022 (riforma del processo civile) resta anche oltre i due anni.
    assert rimasti == {"2022-10-17", "2023-01-13"}
    assert archivio.cerca(Filtri(q='"30 dicembre 2021"'))["totale"] == 0  # tolto anche dall'indice


def test_testo_salvato_si_legge_e_si_cerca(tmp_path):
    archivio = _archivio(tmp_path)
    identificativo = "gu_" + "d" * 24
    archivio.salva_testo(identificativo, testo="Art. 1\nLe imprese agricole beneficiarie della liberta' di stabilimento...",
                         intestazione="DECRETO 6 gennaio 2023", sha256="x", url_testo="https://www.gazzettaufficiale.it/atto/x",
                         articoli=1, letto_il="2026-11-21T12:00:00Z")
    trovati = archivio.cerca(Filtri(q="libertà stabilimento"))
    assert [a["id"] for a in trovati["atti"]] == [identificativo] and trovati["atti"][0]["con_testo"] == 1
    assert "liberta' di stabilimento" in archivio.testo(identificativo)["testo"]
    assert [a["id"] for a in archivio.atti_senza_testo(limite=10)] == ["gu_" + "b" * 24, "gu_" + "c" * 24, "gu_" + "a" * 24]

    from web.services.gazzetta_runtime import testo_dell_atto

    payload = testo_dell_atto(ArchivioGazzetta.in_lettura(archivio.percorso), identificativo)
    assert payload["ok"] and payload["available"] and payload["item"]["hasText"] is True
    assert "libertà di stabilimento" in payload["text"]
    assert testo_dell_atto(archivio, "gu_" + "f" * 24)["notFound"]


def test_accenti_solo_nei_casi_univoci():
    assert accenta("La Camera dei deputati e' convocata per mercoledi' 4 gennaio") == \
        "La Camera dei deputati è convocata per mercoledì 4 gennaio"
    assert accenta("questione di legittimita' costituzionale; piu' di un po' di tempo") == \
        "questione di legittimità costituzionale; più di un po' di tempo"
    assert accenta("PERCHE' E' NULLO") == "PERCHÉ È NULLO"
    # Citazione con apostrofi: non si tocca nulla dopo l'apertura.
    assert accenta("la voce 'Gazzetta' e' cambiata") == "la voce 'Gazzetta' e' cambiata"
    # Con il dizionario: solo se la forma accentata esiste e quella senza accento no.
    parole = {"bontà", "ministero"}
    conosce = parole.__contains__
    assert accenta("la bonta' del Ministero'", conosce) == "la bontà del Ministero'"
    assert accenta("dell'atto e l'udienza") == "dell'atto e l'udienza"


class _Risposta(SimpleNamespace):
    status_code: int = 200


class _Sessione:
    """Il sito ufficiale simulato: pagina dell'atto, «Atto completo» con selezione, modulo di stampa."""

    def __init__(self, con_articoli: bool):
        self.con_articoli = con_articoli
        self.richieste: list[tuple[str, str]] = []

    def get(self, url, timeout=None):
        self.richieste.append(("GET", url))
        if "caricaDettaglioAtto" in url:
            corpo = ('<html><body><a href="/atto/vediMenuHTML?atto.dataPubblicazioneGazzetta=2023-01-03&amp;'
                     'atto.codiceRedazionale=22G00207&amp;tipoSerie=serie_generale&amp;tipoVigenza=originario">Atto completo</a></body></html>')
        elif self.con_articoli:
            corpo = ('<html><body><form id="menuExportForm" action="/atto/stampa/serie_generale/originario" method="post"></form>'
                     '<input type="checkbox" name="articoliSelected" value="art.idArticolo=1" checked="checked"/>'
                     '<input type="checkbox" name="articoliSelected" value="art.idArticolo=2" checked="checked"/>'
                     '<input type="checkbox" name="noteSelected" value="1"/>'
                     '<input type="hidden" name="codiceRedazionale" value="22G00207"/></body></html>')
        else:
            corpo = '<html><body><pre>Convocazione. (23A00087)\n La Camera dei deputati e\' convocata.</pre></body></html>'
        return _Risposta(url=url, content=corpo.encode("utf-8"), status_code=200)

    def post(self, url, data=None, timeout=None):
        self.richieste.append(("POST", url))
        assert ("articoliSelected", "art.idArticolo=2") in data and ("noteSelected", "1") not in data
        corpo = ('<html><body><div id="testa_atto_preview">DECRETO LEGISLATIVO 25 novembre 2022, n. 203</div>'
                 '<pre>Art. 1\n Modifiche al titolo II</pre><pre>Art. 2\n Entrata in vigore</pre>'
                 '<script>var x = 1;</script></body></html>')
        return _Risposta(url=url, content=corpo.encode("utf-8"), status_code=200)


def test_testo_completo_dalla_navigazione_ufficiale():
    url = "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2023-01-03&atto.codiceRedazionale=22G00207"
    sessione = _Sessione(con_articoli=True)
    letto = leggi_testo(url, sessione=sessione)
    assert letto.articoli == 2 and letto.testo == "Art. 1\n Modifiche al titolo II\n\nArt. 2\n Entrata in vigore"
    assert letto.intestazione.startswith("DECRETO LEGISLATIVO") and letto.url_testo.endswith("/atto/stampa/serie_generale/originario")
    assert "action=select-all" in sessione.richieste[1][1]
    semplice = leggi_testo(url, sessione=_Sessione(con_articoli=False))
    assert semplice.articoli == 0 and "convocata" in semplice.testo

    class _Avviso(_Sessione):
        def get(self, url, timeout=None):
            return _Risposta(url=url, status_code=200, content=b"<html><body><pre>Bando di gara - concessioni demaniali</pre></body></html>")

    avviso = leggi_testo(url.replace("serie_generale", "contratti"), sessione=_Avviso(con_articoli=False))
    assert avviso.testo == "Bando di gara - concessioni demaniali" and avviso.url_testo.endswith("22G00207")


def _elenco_annuale(date_numeri):
    collegamenti = "".join(
        f'<a href="/gazzetta/serie_generale/caricaDettaglio?dataPubblicazioneGazzetta={d}&amp;numeroGazzetta={n}">n. {n}</a>'
        for d, n in date_numeri)
    return f"<html><body>{collegamenti}</body></html>".encode()


def test_recupero_storico_riprende_da_dove_si_era_fermato(tmp_path, monkeypatch):
    archivio = ArchivioGazzetta(tmp_path / "gu.sqlite")
    letti: list[str] = []

    def finto_fascicolo(archivio_, serie, fascicolo, *, request_get, quando):
        letti.append(fascicolo.chiave)
        return archivio_.salva_fascicolo(
            {"serie": serie.codice, "numero": fascicolo.numero, "data": fascicolo.data,
             "url_sommario": serie.url_sommario(fascicolo.data, fascicolo.numero), "letto_il": quando},
            [_atto(f"gu_{len(letti):024x}", fascicolo.data, f"DECRETO {fascicolo.data}", "Atto.", numero=fascicolo.numero)])

    elenchi = {2023: [("2023-01-02", "1"), ("2023-01-03", "2"), ("2022-12-31", "303")], 2024: [("2024-01-02", "1")],
               2025: [], 2026: [("2026-11-20", "270")], 2022: [("2022-12-31", "303")]}

    def finta_rete(url, **_):
        anno = int(url.rsplit("/", 1)[1])
        return SimpleNamespace(status_code=200, url=url, content=_elenco_annuale(elenchi[anno]), headers={},
                               iter_content=None)

    monkeypatch.setattr(storico, "_leggi_fascicolo", finto_fascicolo)
    monkeypatch.setattr(storico, "scarica", lambda url, host, request_get: finta_rete(url).content)
    orologio = iter(range(0, 10_000))
    monkeypatch.setattr(storico.time, "monotonic", lambda: next(orologio))
    # Primo tratto: tempo per poche richieste soltanto.
    primo = storico.esegui_tratto(archivio, request_get=finta_rete, adesso=ADESSO, tempo_massimo=4, pausa=0,
                                  serie=[SG], con_testi=False)
    assert primo["sommari"]["completo"] is False and letti == ["SG|2026-11-20|270"]
    secondo = storico.esegui_tratto(archivio, request_get=finta_rete, adesso=ADESSO, tempo_massimo=1000, pausa=0,
                                    serie=[SG], con_testi=False)
    assert letti == ["SG|2026-11-20|270", "SG|2024-01-02|1", "SG|2023-01-03|2", "SG|2023-01-02|1", "SG|2022-12-31|303"]
    assert secondo["sommari"]["fascicoli_nuovi"] == 4
    anni = archivio.anni_letti("SG")
    assert anni[2023]["completo"] == 1 and anni[2024]["completo"] == 1 and anni[2025]["completo"] == 0
    # Terzo tratto: gli anni passati completi non si rileggono, l'anno in corso al più una volta al giorno.
    terzo = storico.esegui_tratto(archivio, request_get=finta_rete, adesso=ADESSO, tempo_massimo=1000, pausa=0,
                                  serie=[SG], con_testi=False)
    assert terzo["sommari"]["fascicoli_nuovi"] == 0 and len(letti) == 5


def test_i_testi_hanno_la_loro_parte_del_tratto(tmp_path, monkeypatch):
    """Collaudo 21/11/2026: i sommari occupavano tutto il tratto e i testi non arrivavano mai («testi_nuovi» 0)."""
    archivio = ArchivioGazzetta(tmp_path / "gu.sqlite")
    scadenze = {}
    orologio = iter(range(0, 100_000, 10))
    monkeypatch.setattr(storico.time, "monotonic", lambda: next(orologio))

    def sommari_infiniti(archivio_, **kw):
        scadenze["sommari"] = kw["scadenza"]
        return {"fascicoli_nuovi": 0, "atti_nuovi": 0, "errori": [], "completo": False}

    def testi(archivio_, **kw):
        scadenze["testi"] = kw["scadenza"]
        return {"testi_nuovi": 1, "errori": 0, "completo": False}

    monkeypatch.setattr(storico, "recupera_sommari", sommari_infiniti)
    monkeypatch.setattr(storico, "recupera_testi", testi)
    storico.esegui_tratto(archivio, adesso=ADESSO, tempo_massimo=1000, pausa=0)
    assert scadenze["testi"] - scadenze["sommari"] == 1000 * (1 - storico.QUOTA_SOMMARI) > 0
