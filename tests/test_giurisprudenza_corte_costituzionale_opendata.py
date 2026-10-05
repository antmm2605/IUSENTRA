"""Import dell'archivio open data della Corte costituzionale nel corpus giurisprudenziale di Lex."""

from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path

from pct.corte_costituzionale_opendata import (
    IMPORT_COMPLETO,
    archivio_completo_presente,
    componi_record,
    corpus_ha_pronunce,
    data_iso,
    importa,
    leggi_massime,
    leggi_pronunce,
    nucleo_dispositivo,
    pulisci_testo,
    scarica,
    url_massime,
    url_pronunce,
)
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from tools import cortecost_importa

PRONUNCE_2025 = [
    {
        "collegio": "composta da:\r\n Presidente: Giovanni AMOROSO; Giudici : Francesco VIGANÒ,&#13;",
        "numero_pronuncia": "6",
        "anno_pronuncia": "2025",
        "data_decisione": "13/01/2025",
        "epigrafe": "ha pronunciato la seguente&#13;nel giudizio per la correzione dell'errore materiale.\r\n Udito il relatore;",
        "relatore_pronuncia": "Giovanni Pitruzzella",
        "testo": "",
        "ecli": "ECLI:IT:COST:2025:6",
        "dispositivo": (
            "per questi motivi\r\n LA CORTE COSTITUZIONALE\r\n dispone la correzione dell'errore materiale "
            "nella sentenza n. 192 del 2024.\r\n Così deciso in Roma, il 13 gennaio 2025.\r\n F.to:\r\n Giovanni AMOROSO"
        ),
        "data_deposito": "27/01/2025",
        "redattore_pronuncia": "Giovanni Pitruzzella",
        "tipologia_pronuncia": "O",
        "presidente": "AMOROSO",
    },
    {
        "collegio": "composta da: Presidente: Giovanni AMOROSO",
        "numero_pronuncia": "1",
        "anno_pronuncia": "2025",
        "data_decisione": "26/11/2024",
        "epigrafe": "ha pronunciato la seguente&#13;SENTENZA nel giudizio di legittimità costituzionale &laquo;doppia pregiudizialità&raquo;",
        "relatore_pronuncia": "Stefano Petitti",
        "testo": "Ritenuto in fatto\r\n 1.- Il Tribunale ha sollevato questioni.",
        "ecli": "ECLI:IT:COST:2025:1",
        "dispositivo": "per questi motivi LA CORTE COSTITUZIONALE dichiara non fondate le questioni. Così deciso in Roma.",
        "data_deposito": "03/01/2025",
        "redattore_pronuncia": "Stefano Petitti",
        "tipologia_pronuncia": "S",
        "presidente": "AMOROSO",
    },
]

PRONUNCE_1990 = [
    {
        "numero_pronuncia": "100",
        "anno_pronuncia": "1990",
        "data_decisione": "21/02/1990",
        "epigrafe": "ha pronunciato la seguente SENTENZA",
        "relatore_pronuncia": "Mario Rossi",
        "testo": "Considerato in diritto: assegno divorzile e tenore di vita.",
        "ecli": "ECLI:IT:COST:1990:100",
        "dispositivo": "per questi motivi LA CORTE COSTITUZIONALE dichiara inammissibile la questione.",
        "data_deposito": "05/03/1990",
        "tipologia_pronuncia": "S",
        "presidente": "SAJA",
    }
]

MASSIME_2025 = """<?xml version="1.0" encoding="UTF-8" standalone="no"?><corte_costituzionale_archiviomassime>
<pronuncia><pronuncia_testata><anno_pronuncia>2025</anno_pronuncia><numero_pronuncia>1</numero_pronuncia>
<tipologia_pronuncia>S</tipologia_pronuncia><data_decisione>26/11/2024</data_decisione><data_deposito>03/01/2025</data_deposito>
<tipologia_giudizio>GIUDIZIO DI LEGITTIMITÀ COSTITUZIONALE IN VIA INCIDENTALE</tipologia_giudizio></pronuncia_testata>
<massime><massima><numero>46620</numero><titolo><![CDATA[Unione europea - Doppia pregiudizialità - Concorso di rimedi]]></titolo>
<testo><![CDATA[Il giudice, ove ravvisi l’incompatibilità del diritto nazionale con il diritto dell’Unione dotato di efficacia diretta, deve individuare il rimedio più appropriato.]]></testo></massima>
<massima><numero>46621</numero><titolo><![CDATA[Processo costituzionale - Rilevanza]]></titolo>
<testo><![CDATA[Il sindacato accentrato coopera con il meccanismo diffuso di attuazione del diritto europeo.]]></testo></massima>
</massime></pronuncia></corte_costituzionale_archiviomassime>"""


def _zip_di_zip(path: Path, interni: dict[str, tuple[str, bytes]]) -> Path:
    """Zip esterno con uno zip annuale per voce: {nome_zip_interno: (nome_file, contenuto)}."""

    esterno = io.BytesIO()
    with zipfile.ZipFile(esterno, "w") as zip_esterno:
        for nome_zip, (nome_file, contenuto) in interni.items():
            interno = io.BytesIO()
            with zipfile.ZipFile(interno, "w") as zip_interno:
                zip_interno.writestr(nome_file, contenuto)
            zip_esterno.writestr(nome_zip, interno.getvalue())
    path.write_bytes(esterno.getvalue())
    return path


def _json_pronunce(righe: list[dict]) -> bytes:
    return json.dumps({"elenco_pronunce": righe}, ensure_ascii=False).encode("cp1252")


def _cartella_open_data(base: Path) -> Path:
    cartella = base / "cortecost"
    cartella.mkdir()
    _zip_di_zip(
        cartella / "P_json2001_oggi.zip",
        {"Cc_Opendata_Pronunce_2025_json.zip": ("Cc_Opendata_Pronunce_2025.json", _json_pronunce(PRONUNCE_2025))},
    )
    _zip_di_zip(
        cartella / "CC_OpenMassime_2001_oggi.zip",
        {"Cc_OpenData_Massime_2025.zip": ("Cc_OpenData_Massime_2025.xml", MASSIME_2025.encode("utf-8"))},
    )
    _zip_di_zip(
        cartella / "P_json1981_2000.zip",
        {"Cc_Opendata_Pronunce_1990_json.zip": ("Cc_Opendata_Pronunce_1990.json", _json_pronunce(PRONUNCE_1990))},
    )
    _zip_di_zip(
        cartella / "P_json1956_1980.zip",
        {"Cc_Opendata_Pronunce_1960_json.zip": ("Cc_Opendata_Pronunce_1960.json", _json_pronunce([]))},
    )
    return cartella


def _riga(db: Path, numero: str, anno: int) -> dict:
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        return dict(
            conn.execute(
                "SELECT * FROM sentenze WHERE organo_giudicante = 'Corte costituzionale' AND numero_sentenza = ? AND anno_sentenza = ?",
                (numero, anno),
            ).fetchone()
        )


def test_pulizia_testo_e_dispositivo():
    assert pulisci_testo("ha pronunciato la seguente&#13;nel giudizio\r\n  Udito &laquo;x&raquo;") == (
        "ha pronunciato la seguente\nnel giudizio\nUdito «x»"
    )
    assert nucleo_dispositivo(PRONUNCE_2025[0]["dispositivo"]) == (
        "dispone la correzione dell'errore materiale nella sentenza n. 192 del 2024."
    )
    assert data_iso("27/01/2025") == "2025-01-27"
    assert data_iso("31/02/2025") == ""


def test_lettura_zip_di_zip_e_unione_massime(tmp_path: Path):
    cartella = _cartella_open_data(tmp_path)
    pronunce = list(leggi_pronunce(cartella / "P_json2001_oggi.zip"))
    massime = leggi_massime(cartella / "CC_OpenMassime_2001_oggi.zip")
    assert [p["numero_pronuncia"] for p in pronunce] == ["6", "1"]
    assert pronunce[0]["collegio"].startswith("composta da:")
    assert list(massime) == [(2025, 1)]
    assert [m["numero"] for m in massime[(2025, 1)]["massime"]] == ["46620", "46621"]
    assert list(leggi_pronunce(cartella / "P_json2001_oggi.zip", dal_anno=2026)) == []


def test_componi_record_sentenza_con_massime():
    record = componi_record(PRONUNCE_2025[1], leggi_massime_da_testo())
    assert record["titolo"] == "Corte costituzionale, sentenza n. 1/2025"
    assert record["tipo_provvedimento"] == "sentenza"
    assert record["oggetto"] == "Giudizio di legittimità costituzionale in via incidentale"
    assert record["massima_ufficiale"].startswith("Il giudice, ove ravvisi")
    assert "Il sindacato accentrato" in record["massima_ufficiale"]
    assert record["principio_sintetico"] == "dichiara non fondate le questioni."
    assert record["url_pagina_ufficiale"] == "https://www.cortecostituzionale.it/scheda-pronuncia/2025/1"
    assert "&#13;" not in record["testo_integrale"] and "\r" not in record["testo_integrale"]
    assert "«doppia pregiudizialità»" in record["testo_integrale"]
    assert record["data_decisione"] == "2024-11-26" and record["data_deposito"] == "2025-01-03"
    assert record["stato_verifica"] == "verificata" and record["fonte_ufficiale_confermata"] is True
    assert [m["numero_massima"] for m in record["massime"]] == ["46620", "46621"]


def leggi_massime_da_testo() -> dict:
    import xml.etree.ElementTree as ET

    radice = ET.fromstring(MASSIME_2025.encode("utf-8"))
    voci = []
    for massima in radice.iter("massima"):
        voci.append(
            {
                "numero": massima.findtext("numero"),
                "titolo": massima.findtext("titolo"),
                "testo": massima.findtext("testo"),
            }
        )
    return {"tipologia_giudizio": "GIUDIZIO DI LEGITTIMITÀ COSTITUZIONALE IN VIA INCIDENTALE", "massime": voci}


def test_import_scrive_il_corpus_con_massime_fts_e_scheda(tmp_path: Path):
    cartella = _cartella_open_data(tmp_path)
    db = tmp_path / "corpus" / "giurisprudenza_corpus.db"
    esito = importa(
        [(cartella / "P_json2001_oggi.zip", cartella / "CC_OpenMassime_2001_oggi.zip")],
        [db],
        blocco=1,
    )
    assert esito.pronunce_lette == 2 and esito.inserite == 2 and esito.massime == 2 and esito.con_massime == 1

    ordinanza = _riga(db, "6", 2025)
    assert ordinanza["titolo"] == "Corte costituzionale, ordinanza n. 6/2025"
    assert ordinanza["tipo_provvedimento"] == "ordinanza"
    assert ordinanza["ecli"] == "ECLI:IT:COST:2025:6"
    assert ordinanza["relatore"] == "Giovanni Pitruzzella"
    assert ordinanza["presidente"] == "AMOROSO"
    assert ordinanza["collegio"].startswith("Presidente: Giovanni AMOROSO")
    assert ordinanza["data_deposito"] == "2025-01-27"
    assert ordinanza["stato_verifica"] == "verificata"
    assert ordinanza["fonte_ufficiale_confermata"] == 1 and ordinanza["testo_integrale_presente"] == 1

    corpus = GestioneCorpusGiurisprudenza(str(db))
    trovate = corpus.cerca_sentenze(q="doppia pregiudizialità diritto dell'Unione", limit=3)
    assert trovate and trovate[0]["ecli"] == "ECLI:IT:COST:2025:1"
    assert trovate[0]["tipo_provvedimento"] == "sentenza"
    assert trovate[0]["relatore"] == "Stefano Petitti"
    assert trovate[0]["esito"] == "dichiara non fondate le questioni."
    scheda = corpus.get_sentenza(trovate[0]["id"])
    assert [m["numero_massima"] for m in scheda["massime"]] == ["46620", "46621"]
    assert all(m["ufficiale"] == 1 and m["stato_verifica"] == "verificata" for m in scheda["massime"])
    assert scheda["fonte_codice"] == "corte_costituzionale" and scheda["tipo_fonte"] == "ufficiale"
    assert corpus.can_cite_sentenza(scheda) is True
    assert corpus_ha_pronunce(db) == 2
    # import parziale: nessun segno di archivio completo
    assert archivio_completo_presente(db) is False


def test_import_idempotente_salta_invariate_e_rileva_modifiche(tmp_path: Path):
    cartella = _cartella_open_data(tmp_path)
    db = tmp_path / "giurisprudenza_corpus.db"
    coppie = [(cartella / "P_json2001_oggi.zip", cartella / "CC_OpenMassime_2001_oggi.zip")]
    importa(coppie, [db])
    secondo = importa(coppie, [db])
    assert (secondo.inserite, secondo.aggiornate, secondo.invariate) == (0, 0, 2)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sentenze").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM massime").fetchone()[0] == 2

    # pronuncia corretta nel dataset: si aggiorna senza duplicare
    modificate = [dict(PRONUNCE_2025[0], dispositivo="per questi motivi LA CORTE COSTITUZIONALE dispone altro."), PRONUNCE_2025[1]]
    _zip_di_zip(
        cartella / "P_json2001_oggi.zip",
        {"Cc_Opendata_Pronunce_2025_json.zip": ("Cc_Opendata_Pronunce_2025.json", _json_pronunce(modificate))},
    )
    terzo = importa(coppie, [db])
    assert (terzo.inserite, terzo.aggiornate, terzo.invariate) == (0, 1, 1)
    assert _riga(db, "6", 2025)["principio_sintetico"] == "dispone altro."


def test_import_riprende_la_riga_del_vecchio_sincronizzatore(tmp_path: Path):
    db = tmp_path / "giurisprudenza_corpus.db"
    corpus = GestioneCorpusGiurisprudenza(str(db))
    corpus.salva_sentenza(
        {
            "fonte": {"codice": "corte_costituzionale", "nome": "Corte costituzionale", "tipo_fonte": "ufficiale"},
            "uuid_interno": "corte_costituzionale:2025:6",
            "organo_giudicante": "Corte costituzionale",
            "numero_sentenza": "6/2025",
            "anno_sentenza": 2025,
            "tipo_provvedimento": "ordinanza",
            "titolo": "Ordinanza n. 6/2025 - Corte costituzionale",
            "url_pagina_ufficiale": "https://www.cortecostituzionale.it/",
        }
    )
    cartella = _cartella_open_data(tmp_path)
    esito = importa([(cartella / "P_json2001_oggi.zip", None)], [db])
    assert (esito.inserite, esito.aggiornate) == (1, 1)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sentenze").fetchone()[0] == 2
    assert _riga(db, "6", 2025)["ecli"] == "ECLI:IT:COST:2025:6"


def test_tool_import_completo_json_e_se_assente(tmp_path: Path, capsys):
    cartella = _cartella_open_data(tmp_path)
    tenant = tmp_path / "tenants" / "studio-a"
    db = tmp_path / "globale_corpus.db"
    argomenti = ["--cartella", str(cartella), "--db", str(db), "--tenant-dir", str(tenant), "--json"]

    assert cortecost_importa.main(argomenti) == 0
    riepilogo = json.loads(capsys.readouterr().out)
    assert riepilogo["pronunce_lette"] == 3
    assert riepilogo["inserite"] == 6  # 3 pronunce in 2 corpus
    corpus_tenant = tenant / "intelligence" / "giurisprudenza_corpus.db"
    assert archivio_completo_presente(db) and archivio_completo_presente(corpus_tenant)
    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM importazioni_giurisprudenza WHERE query_origine = ?", (IMPORT_COMPLETO,)
        ).fetchone()[0] == 1

    assert cortecost_importa.main(argomenti[:-1] + ["--se-assente"]) == 0
    assert "Nulla da importare" in capsys.readouterr().out


def test_tool_dry_run_e_anni_recenti_non_scrivono(tmp_path: Path, capsys):
    cartella = _cartella_open_data(tmp_path)
    db = tmp_path / "corpus.db"
    assert cortecost_importa.main(["--cartella", str(cartella), "--db", str(db), "--dry-run", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["pronunce_lette"] == 3
    assert not db.exists()

    assert cortecost_importa.main(
        ["--cartella", str(cartella), "--db", str(db), "--periodi", "2001_oggi", "--dal-anno", "2026", "--json"]
    ) == 0
    assert json.loads(capsys.readouterr().out)["pronunce_lette"] == 0
    assert archivio_completo_presente(db) is False


def test_tool_download_non_riuscito_esce_con_codice_2(tmp_path: Path, monkeypatch, capsys):
    def _fallisce(*_args, **_kwargs):
        raise OSError("rete non raggiungibile")

    monkeypatch.setattr(cortecost_importa, "scarica", _fallisce)
    codice = cortecost_importa.main(["--cartella", str(tmp_path / "vuota"), "--db", str(tmp_path / "c.db"), "--scarica"])
    assert codice == 2
    assert "download open data" in capsys.readouterr().err


def test_scarica_usa_gli_url_ufficiali_e_scrive_zip(tmp_path: Path):
    richieste: list[str] = []
    contenuto = io.BytesIO()
    with zipfile.ZipFile(contenuto, "w") as archivio:
        archivio.writestr("vuoto.txt", "x")

    class _Risposta:
        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=0):
            yield contenuto.getvalue()

    def _getter(url, **kwargs):
        richieste.append(url)
        assert kwargs.get("stream") is True and "verify" not in kwargs
        return _Risposta()

    scaricati = scarica(tmp_path, ["2001_oggi"], getter=_getter)
    assert richieste == [url_pronunce("2001_oggi"), url_massime("2001_oggi")]
    assert richieste[0] == "https://dati.cortecostituzionale.it/opendata/distribuzione/pronunce/P_json2001_oggi.zip"
    assert richieste[1] == "https://dati.cortecostituzionale.it/opendata/distribuzione/CC_OpenMassime_2001_oggi.zip"
    assert [p.name for p in scaricati] == ["P_json2001_oggi.zip", "CC_OpenMassime_2001_oggi.zip"]


def test_corpus_dei_tenant_dal_registro(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("PCT_GIURISPRUDENZA_DB", raising=False)
    (tmp_path / "tenants" / "studio-b").mkdir(parents=True)
    percorsi = cortecost_importa.corpus_dei_tenant(str(tmp_path / "manca.json"), str(tmp_path))
    assert percorsi == [
        str(tmp_path / "intelligence" / "giurisprudenza_corpus.db"),
        str(tmp_path / "tenants" / "studio-b" / "intelligence" / "giurisprudenza_corpus.db"),
    ]
