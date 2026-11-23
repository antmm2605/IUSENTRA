"""Testo integrale delle sentenze del Consiglio di Stato, del CGA e dei TAR dal sito ufficiale (estremi da OpenGA)."""
import sqlite3
from types import SimpleNamespace

from pct.giustizia_amministrativa_testi import (
    ArchivioTestiGA,
    leggi,
    leggi_subito,
    sedi_dai_fascicoli,
    sedi_dell_organo,
)
from pct.giustizia_amministrativa_testi import testo_su_richiesta as su_richiesta

PAGINA = ("<html><body><p>Pubblicato il 11/03/2020</p><p>REPUBBLICA ITALIANA</p><p>IN NOME DEL POPOLO ITALIANO</p>"
          "<p>Il Consiglio di Stato in sede giurisdizionale (Sezione Sesta) ha pronunciato la presente SENTENZA sul ricorso "
          "numero di registro generale 4232 del 2019, proposto da ... per l'esecuzione del giudicato ... annullamento del "
          "titolo edilizio e dell'assenso paesistico ... " + "motivazione " * 40 + "</p><script>x()</script></body></html>")


def _pagina_tar(numero="01731/2025", ricorso="00012/2025"):
    return (f"<html><body><p>Pubblicato il 03/02/2025</p><p>N. {numero}REG.PROV.COLL.</p><p>N. {ricorso} REG.RIC.</p>"
            "<p>REPUBBLICA ITALIANA</p><p>Il Tribunale Amministrativo Regionale per il Lazio ... " + "motivazione " * 40
            + "</p></body></html>")


def _righe():
    return [
        {"sede": "002", "nome_sede": "CdS GIURISDIZIONALE - ROMA", "tipo": "SENTENZA", "numero": "202001731", "anno": 2020,
         "ricorso": "201904232", "oggetto": "ESECUZIONE SENTENZA - ASSENSO PAESISTICO", "esito": "RESPINGE"},
        {"sede": "002", "nome_sede": "CdS GIURISDIZIONALE - ROMA", "tipo": "SENTENZA", "numero": "202607168", "anno": 2026,
         "ricorso": "202603768", "oggetto": "APPALTI", "esito": ""},
        {"sede": "032", "nome_sede": "CGA GIURISDIZIONALE - PALERMO", "tipo": "SENTENZA BREVE", "numero": "202600659",
         "anno": 2026, "ricorso": "202600141", "oggetto": "EDILIZIA", "esito": ""},
        {"sede": "027", "nome_sede": "TAR TRENTINO ALTO ADIGE - TRENTO", "tipo": "SENTENZA", "numero": "202400191",
         "anno": 2024, "ricorso": "202400095", "oggetto": "VIGILI DEL FUOCO", "esito": ""},
    ]


def test_coda_testo_ricerca_e_404(tmp_path):
    archivio = ArchivioTestiGA(tmp_path / "ga.sqlite")
    assert archivio.carica_estremi(_righe(), anno_corrente=2026) == 4
    assert archivio.carica_estremi(_righe(), anno_corrente=2026) == 0
    coda = archivio.da_leggere()
    # Ultimi tre anni prima (Consiglio di Stato, poi TAR), poi i più vecchi; la sentenza breve del CGA in fondo.
    assert [c["id"].split("|")[-1] for c in coda] == ["202607168", "202400191", "202001731", "202600659"]
    assert coda[1]["url"] == ("https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&schema=tar_tn&nrg=202400095"
                              "&nomeFile=202400191_01.html&subDir=Provvedimenti")
    assert coda[2]["url"] == ("https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&schema=cds&nrg=201904232"
                              "&nomeFile=202001731_11.html&subDir=Provvedimenti")

    def scarica(url):
        if "202001731" in url or "202600659" in url:
            return SimpleNamespace(status_code=200, url=url, content=PAGINA.encode())
        return SimpleNamespace(status_code=200, url="https://mdp.giustizia-amministrativa.it/visualizza/404.html", content=b"")

    esito = leggi(archivio, scarica=scarica, tempo_massimo=60, pausa=0)
    assert esito == {"letti": 2, "errori": 2, "da_ritentare": 0}
    assert archivio.conteggi() == {"letto": 2, "non_disponibile": 2}
    trovati = archivio.cerca("assenso paesistico")
    assert [t["numero"] for t in trovati] and trovati[0]["pubblicato_il"] == "11/03/2020"
    assert archivio.da_leggere() == []
    assert coda[3]["url"].count("schema=cgagiur&") == 1


def _sentenza(sede, nome, numero, anno, tipo="SENTENZA", ricorso="202400001"):
    return {"sede": sede, "nome_sede": nome, "tipo": tipo, "numero": numero, "anno": anno, "ricorso": ricorso,
            "oggetto": "", "esito": ""}


def test_ordine_della_coda_voluto_dallo_studio(tmp_path):
    """CdS, CGA, TAR Calabria e Lazio, TAR dei fascicoli, altri TAR; ultimi tre anni prima; brevi in fondo."""
    archivio = ArchivioTestiGA(tmp_path / "ga.sqlite")
    righe = [
        _sentenza("021", "TAR PUGLIA - BARI", "202600010", 2026),
        _sentenza("030", "TAR VENETO - VENEZIA", "202600020", 2026),
        _sentenza("003", "TAR LAZIO - ROMA", "202600030", 2026),
        _sentenza("009", "TAR CALABRIA - REGGIO CALABRIA", "202500040", 2025),
        _sentenza("008", "TAR CALABRIA - CATANZARO", "202600050", 2026),
        _sentenza("032", "CGA GIURISDIZIONALE - PALERMO", "202600060", 2026),
        _sentenza("002", "CdS GIURISDIZIONALE - ROMA", "202600070", 2026),
        _sentenza("002", "CdS GIURISDIZIONALE - ROMA", "201900080", 2019),
        _sentenza("008", "TAR CALABRIA - CATANZARO", "202000090", 2020),
        _sentenza("002", "CdS GIURISDIZIONALE - ROMA", "202600100", 2026, tipo="SENTENZA BREVE"),
    ]
    archivio.carica_estremi(righe, anno_corrente=2026)
    archivio.imposta_sedi_studio(sedi_dai_fascicoli(["Tar venezia", "TRIBUNALE DI TARANTO"]), da="test")
    assert archivio.sedi_studio() == {"030"}
    archivio.riordina(anno_corrente=2026)
    assert [c["id"].split("|")[-1] for c in archivio.da_leggere()] == [
        "202600070", "202600060", "202600050", "202600030", "202500040", "202600020", "202600010",
        "201900080", "202000090", "202600100"]


def test_sedi_dagli_uffici_dei_fascicoli():
    uffici = ["TAR Calabria", "TAR LAZIO", "TAR VENEZIA", "TAR di Reggio Calabria",
              "TRIBUNALE AMMINISTRATIVO REGIONALE DELLA CALABRIA - REGGIO CALABRIA", "TRIBUNALE DI TARANTO",
              "Tribunale amministrativo del Veneto", "Tar della Calabria sede di Reggio Calabria", "TAR Emilia-Romagna",
              "Tribunale di Roma", "Corte d'appello di Catanzaro"]
    assert sedi_dai_fascicoli(uffici) == {"008", "003", "030", "009", "012"}
    assert sedi_dell_organo("Consiglio di Stato") == {"002"} and sedi_dell_organo("CGA") == {"032"}
    assert sedi_dell_organo("TAR LAZIO - LATINA") == {"001"} and sedi_dell_organo("") is None


class _Tempo(Exception):
    pass


def test_lettura_immediata_su_richiesta(tmp_path):
    archivio = ArchivioTestiGA(tmp_path / "ga.sqlite")
    archivio.carica_estremi(_righe(), anno_corrente=2026)
    chiamate = []

    def scarica(url, *, timeout):
        chiamate.append((url, timeout))
        if "202001731" in url:
            return SimpleNamespace(status_code=200, url=url, content=PAGINA.encode())
        if "202607168" in url:
            return SimpleNamespace(status_code=200, url="https://mdp.giustizia-amministrativa.it/visualizza/404.html", content=b"")
        raise _Tempo("read timeout")

    # Dalla ricerca: «Consiglio di Stato n. 1731/2020», testo letto ora dal sito e salvato nell'archivio.
    esito = su_richiesta(archivio, organo="Consiglio di Stato", anno=2020, numero="1731", scarica=scarica, tempo_massimo=8)
    assert esito["ok"] and esito["fonte"] == "sito ufficiale, letto ora" and "REPUBBLICA ITALIANA" in esito["testo"]
    assert chiamate[-1][1] == 8 and esito["pubblicato_il"] == "11/03/2020"
    # La seconda volta si legge dall'archivio, senza scaricare.
    di_nuovo = su_richiesta(archivio, organo="Consiglio di Stato", anno=2020, numero="202001731", scarica=scarica)
    assert di_nuovo["fonte"] == "archivio" and len(chiamate) == 1
    assert archivio.cerca("assenso paesistico")[0]["numero"] == "202001731"
    # Non pubblicato sul sito: messaggio chiaro e voce chiusa.
    assente = su_richiesta(archivio, organo="CdS", anno=2026, numero="7168", scarica=scarica)
    assert not assente["ok"] and "non è pubblicato" in assente["messaggio"]
    # Sito lento: tempo massimo, messaggio chiaro, la voce resta in coda.
    lento = leggi_subito(archivio, "027|SENTENZA|2024|202400191", scarica=scarica, tempo_massimo=5)
    assert not lento["ok"] and "entro 5 secondi" in lento["messaggio"]
    assert archivio.provvedimento("027|SENTENZA|2024|202400191")["stato"] == "da_leggere"
    # Estremi completi dalla ricerca OpenGA ma non ancora in archivio: si salvano solo perché il testo ufficiale
    # riporta gli stessi numeri di sentenza e di ricorso; la voce resta provvisoria.
    nuovo = su_richiesta(archivio, organo="TAR LAZIO - ROMA", anno=2025, numero="1731", ricorso="202500012",
                         scarica=lambda url, timeout: SimpleNamespace(status_code=200, url=url, content=_pagina_tar().encode()))
    assert nuovo["ok"] and nuovo["id"] == "003|SENTENZA|2025|202501731"
    assert "schema=tar_rm&nrg=202500012&nomeFile=202501731_01.html" in nuovo["url"]
    voce = archivio.provvedimento("003|SENTENZA|2025|202501731")
    assert voce["provvisoria"] == 1 and voce["nome_sede"] == "TAR LAZIO - ROMA"
    # Numero presente in più TAR senza sede: si chiede la sede, non si sceglie a caso.
    archivio.carica_estremi([_sentenza("021", "TAR PUGLIA - BARI", "202501731", 2025)])
    doppio = su_richiesta(archivio, organo="TAR", anno=2025, numero="1731", scarica=scarica)
    assert not doppio["ok"] and "indica il TAR" in doppio["messaggio"]
    assert not su_richiesta(archivio, organo="CdS", anno=2025, numero="99999", scarica=scarica)["ok"]


def test_correzione_schema_cga_nelle_voci_esistenti(tmp_path):
    percorso = tmp_path / "ga.sqlite"
    ArchivioTestiGA(percorso)
    with sqlite3.connect(percorso) as conn:
        conn.execute("INSERT INTO provvedimenti (id, sede, nome_sede, schema, tipo, numero, anno, ricorso, url, stato, tentativi) "
                     "VALUES ('032|SENTENZA|2025|202500161', '032', 'CGA GIURISDIZIONALE - PALERMO', 'cga', 'SENTENZA', "
                     "'202500161', 2025, '202400001', 'https://x/?nodeRef=&schema=cga&nrg=202400001&nomeFile=202500161_11.html', "
                     "'non_disponibile', 1)")
    voce = ArchivioTestiGA(percorso).provvedimento("032|SENTENZA|2025|202500161")
    assert voce["schema"] == "cgagiur" and "schema=cgagiur&" in voce["url"]
    assert voce["stato"] == "da_leggere" and voce["tentativi"] == 0


def test_api_lettura_su_richiesta(tmp_path, monkeypatch):
    from flask import Flask, g

    import pct.giustizia_amministrativa_testi as modulo
    from web.blueprints.api_v1_prassi import api_v1_prassi

    ArchivioTestiGA(tmp_path / "ga.sqlite").carica_estremi(_righe(), anno_corrente=2026)
    monkeypatch.setattr(modulo, "scarica_ufficiale",
                        lambda url, *, timeout=15: SimpleNamespace(status_code=200, url=url, content=PAGINA.encode()))
    app = Flask(__name__)
    app.config["PCT_GA_TESTI_DB"] = str(tmp_path / "ga.sqlite")
    app.register_blueprint(api_v1_prassi)
    app.before_request(lambda: setattr(g, "utente_corrente", object()))
    client = app.test_client()
    pagina = client.get("/api/v1/ui/giustizia-amministrativa/testo/pagina?organo=TAR%20VENETO&anno=2025&numero=5")
    assert pagina.status_code == 200 and "non è nel catalogo" in pagina.get_data(as_text=True)
    assert client.get("/api/v1/ui/giustizia-amministrativa/testo?anno=xx&numero=1").get_json()["message"]
    subito = client.get("/api/v1/ui/giustizia-amministrativa/testo?organo=Consiglio%20di%20Stato&anno=2020&numero=1731").get_json()
    assert subito["ok"] and subito["source"] == "sito ufficiale, letto ora" and "REPUBBLICA ITALIANA" in subito["text"]
    lettore = client.get("/api/v1/ui/giustizia-amministrativa/testo/pagina?organo=CdS&anno=2020&numero=1731").get_data(as_text=True)
    assert "IN NOME DEL POPOLO ITALIANO" in lettore and "dall'archivio" not in lettore and "<script>" not in lettore


def _scritture(percorso):
    with sqlite3.connect(percorso) as conn:
        return conn.execute("SELECT COUNT(*) FROM provvedimenti").fetchone()[0], conn.execute(
            "SELECT COUNT(*) FROM provvedimenti_fts").fetchone()[0]


def test_lettura_su_richiesta_non_scrive_estremi_non_verificati(tmp_path):
    percorso = tmp_path / "ga.sqlite"
    archivio = ArchivioTestiGA(percorso)
    chiamate = []

    def scarica(url, *, timeout):
        chiamate.append(url)
        return SimpleNamespace(status_code=200, url=url, content=_pagina_tar().encode())

    prima = _scritture(percorso)
    # Sede inventata o fuori elenco: rifiutata prima di toccare la rete.
    for sede in ("999", "031", "../x", "TAR"):
        esito = su_richiesta(archivio, sede=sede, anno=2025, numero="1731", ricorso="202500012", scarica=scarica)
        assert not esito["ok"] and "Sede non riconosciuta" in esito["messaggio"]
    # Organo incoerente con la sede: rifiutato.
    incoerente = su_richiesta(archivio, sede="003", organo="Consiglio di Stato", anno=2025, numero="1731",
                              ricorso="202500012", scarica=scarica)
    assert not incoerente["ok"] and "non corrisponde" in incoerente["messaggio"]
    assert chiamate == []
    # Estremi falsi: la pagina scaricata riporta un'altra sentenza o un altro ricorso → nessuna scrittura.
    for pagina in (_pagina_tar(numero="01732/2025"), _pagina_tar(ricorso="00013/2025"), "<html>404</html>"):
        falso = su_richiesta(archivio, sede="003", organo="TAR Lazio", anno=2025, numero="1731", ricorso="202500012",
                             scarica=lambda url, timeout, p=pagina: SimpleNamespace(status_code=200, url=url, content=p.encode()))
        assert not falso["ok"] and "non è stata salvata" in falso["messaggio"]
    non_pubblicata = su_richiesta(archivio, sede="003", anno=2025, numero="1731", ricorso="202500012",
                                  scarica=lambda url, timeout: SimpleNamespace(
                                      status_code=200, url="https://mdp.giustizia-amministrativa.it/visualizza/404.html", content=b""))
    assert not non_pubblicata["ok"]
    lento = su_richiesta(archivio, sede="003", anno=2025, numero="1731", ricorso="202500012",
                         scarica=lambda url, timeout: (_ for _ in ()).throw(TimeoutError("lento")))
    assert not lento["ok"] and "entro" in lento["messaggio"]
    # Senza ricorso né catalogo: nessuna lettura e nessuna scrittura.
    assert not su_richiesta(archivio, sede="003", anno=2025, numero="1731", scarica=scarica)["ok"]
    assert _scritture(percorso) == prima == (0, 0)


def _catalogo(percorso, righe):
    with sqlite3.connect(percorso) as conn:
        conn.execute("CREATE TABLE righe (sede TEXT, nome_sede TEXT, tipo TEXT, numero TEXT, anno INTEGER, ricorso TEXT, "
                     "oggetto TEXT, esito_originale TEXT)")
        conn.executemany("INSERT INTO righe VALUES (?,?,?,?,?,?,?,?)",
                         [(r["sede"], r["nome_sede"], r["tipo"], r["numero"], r["anno"], r["ricorso"], r["oggetto"], r["esito"])
                          for r in righe])


def test_estremi_dal_catalogo_e_voce_provvisoria_sostituita(tmp_path):
    catalogo = tmp_path / "catalogo.db"
    breve = {**_sentenza("003", "TAR LAZIO - ROMA", "202501731", 2025, tipo="SENTENZA BREVE", ricorso="202500012"),
             "oggetto": "SILENZIO", "esito": "ACCOGLIE"}
    _catalogo(catalogo, [breve, _sentenza("021", "TAR PUGLIA - BARI", "202500500", 2025, ricorso="202400100")])
    archivio = ArchivioTestiGA(tmp_path / "ga.sqlite")
    pagina = lambda url, timeout: SimpleNamespace(status_code=200, url=url, content=_pagina_tar().encode())  # noqa: E731
    # Dal catalogo (senza ricorso): la voce entra con gli estremi ufficiali, poi si legge.
    bari = su_richiesta(archivio, organo="TAR Puglia - Bari", anno=2025, numero="500", catalogo=catalogo,
                        scarica=lambda url, timeout: SimpleNamespace(status_code=200, url=url, content=PAGINA.encode()))
    assert bari["ok"] and bari["id"] == "021|SENTENZA|2025|202500500"
    assert archivio.provvedimento(bari["id"])["provvisoria"] == 0
    # Provvisoria (catalogo non ancora aggiornato), poi l'importazione del catalogo la sostituisce.
    prov = su_richiesta(archivio, sede="003", anno=2025, numero="1731", ricorso="202500012", scarica=pagina)
    assert prov["ok"] and prov["id"] == "003|SENTENZA|2025|202501731"
    archivio.carica_estremi([breve], anno_corrente=2026)
    assert archivio.provvedimento("003|SENTENZA|2025|202501731") is None
    ufficiale = archivio.provvedimento("003|SENTENZA BREVE|2025|202501731")
    assert ufficiale["stato"] == "letto" and ufficiale["oggetto"] == "SILENZIO" and "REG.PROV.COLL" in ufficiale["testo"]
    assert [t["id"] for t in archivio.cerca("motivazione")].count("003|SENTENZA BREVE|2025|202501731") == 1
    # Stessa chiave: il catalogo aggiorna gli estremi della provvisoria e la rende definitiva.
    prov2 = su_richiesta(archivio, sede="003", anno=2025, numero="1999", ricorso="202500012",
                         scarica=lambda url, timeout: SimpleNamespace(status_code=200, url=url,
                                                                       content=_pagina_tar(numero="01999/2025").encode()))
    assert prov2["ok"]
    archivio.carica_estremi([{**_sentenza("003", "TAR LAZIO - ROMA", "202501999", 2025, ricorso="202500012"),
                              "oggetto": "APPALTI"}])
    voce = archivio.provvedimento("003|SENTENZA|2025|202501999")
    assert voce["provvisoria"] == 0 and voce["oggetto"] == "APPALTI" and voce["stato"] == "letto"


def test_timeout_di_un_testo_non_ferma_il_giro(tmp_path):
    archivio = ArchivioTestiGA(tmp_path / "ga.sqlite")
    archivio.carica_estremi(_righe(), anno_corrente=2026)
    chiamate: dict[str, int] = {}
    attese: list[float] = []

    def scarica(url):
        chiamate[url] = chiamate.get(url, 0) + 1
        if "202607168" in url:
            raise TimeoutError("The read operation timed out")
        if "202400191" in url and chiamate[url] == 1:
            raise ConnectionError("connessione chiusa")  # la riprova riesce
        return SimpleNamespace(status_code=200, url=url, content=PAGINA.encode())

    esito = leggi(archivio, scarica=scarica, tempo_massimo=60, pausa=0, dormi=attese.append)
    assert esito == {"letti": 3, "errori": 0, "da_ritentare": 1}
    assert attese == [5.0, 15.0, 5.0]
    voce = archivio.provvedimento("002|SENTENZA|2026|202607168")
    assert voce["stato"] == "da_leggere" and voce["tentativi"] == 0 and "TimeoutError" in voce["messaggio"]
    assert [v["id"] for v in archivio.da_leggere()] == ["002|SENTENZA|2026|202607168"]
