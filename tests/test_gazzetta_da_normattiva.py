"""Testo degli atti normativi della Gazzetta dalla biblioteca Normattiva: stesso codice redazionale e stesso numero."""
import sqlite3

from pct.gazzetta.archivio import ArchivioGazzetta
from pct.gazzetta.da_normattiva import collega
from pct.gazzetta.serie import PER_CODICE

SG = PER_CODICE["SG"]


def _atto(ident, codice, numero, data_atto, intestazione):
    return {"id": ident, "serie": "SG", "numero_gu": "260", "data_gu": "2026-11-09", "rubrica": "", "emittente": "",
            "intestazione": intestazione, "tipo": "legge", "numero_atto": numero, "data_atto": data_atto, "descrizione": "",
            "codice_redazionale": codice, "pagina": "1", "posizione": 0, "url": "https://www.gazzettaufficiale.it/atto/x",
            "url_sommario": SG.url_sommario("2026-11-09", "260"), "acquisito_il": "x"}


def _normattiva(percorso):
    conn = sqlite3.connect(percorso)
    conn.execute("CREATE TABLE normative_documents (id INTEGER PRIMARY KEY, collection_name TEXT, xml_entry TEXT, numero TEXT, "
                 "data_atto TEXT, urn TEXT, redazione_id TEXT)")
    conn.execute("CREATE TABLE normative_articles (id INTEGER PRIMARY KEY, document_id INTEGER, article_number TEXT, article_text TEXT)")
    conn.executemany("INSERT INTO normative_documents VALUES (?,?,?,?,?,?,?)", [
        (1, "Normattiva AKN riscontrato", "2026-11-09_26G00222_ORIGINALE_V0.xml", "203", "2026-10-30",
         "urn:nir:stato:legge:2026-10-30;203", "2026-11-10"),
        (2, "Normattiva AKN riscontrato", "2026-11-09_26G00222_VIGENZA_2026-11-20_V1.xml", "203", "2026-10-30",
         "urn:nir:stato:legge:2026-10-30;203", "2026-11-20"),
        (3, "Normattiva AKN riscontrato", "2026-11-10_26G00223_ORIGINALE_V0.xml", "999", "2026-10-31",
         "urn:nir:stato:legge:2026-10-31;999", "2026-11-10"),
    ])
    conn.executemany("INSERT INTO normative_articles VALUES (?,?,?,?)", [
        (1, 1, "1", "Art. 1. Testo originario."), (2, 1, "2", "Art. 2. Entrata in vigore."),
        (3, 2, "1", "Art. 1. Testo modificato."), (4, 3, "1", "Art. 1. Altro atto."),
    ])
    conn.commit()
    conn.close()


def test_collega_solo_con_codice_e_numero_coincidenti_e_preferisce_l_originale(tmp_path):
    archivio = ArchivioGazzetta(tmp_path / "gu.sqlite")
    archivio.salva_fascicolo({"serie": "SG", "numero": "260", "data": "2026-11-09", "url_sommario": "u", "letto_il": "x"}, [
        _atto("gu_" + "a" * 24, "26G00222", "203", "2026-10-30", "LEGGE 30 ottobre 2026, n. 203"),
        _atto("gu_" + "b" * 24, "26G00223", "204", "2026-10-31", "LEGGE 31 ottobre 2026, n. 204"),  # numero diverso
        _atto("gu_" + "c" * 24, "26G00299", "205", "2026-11-01", "LEGGE 1 novembre 2026, n. 205"),  # non in biblioteca
        _atto("gu_" + "d" * 24, "26A06001", "", "", "DECRETO 2 novembre 2026"),  # atto «A»: dal sito
    ])
    _normattiva(tmp_path / "n.sqlite")
    esito = collega(archivio, tmp_path / "n.sqlite")
    assert esito == {"candidati": 3, "collegati": 1, "non_in_biblioteca": 1, "numero_discorde": 1}
    testo = archivio.testo("gu_" + "a" * 24)
    assert testo["testo"] == "Art. 1. Testo originario.\n\nArt. 2. Entrata in vigore." and testo["articoli"] == 2
    assert testo["fonte"] == "Normattiva, testo originario (codice redazionale 26G00222)"
    assert testo["url_testo"] == "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2026-10-30;203"
    # Il recupero dal sito salta l'atto collegato e scarica il resto.
    da_scaricare = {a["id"][3] for a in archivio.atti_senza_testo(limite=10)}
    assert da_scaricare == {"b", "c", "d"}
    # Di nuovo: nulla da fare, nessun doppione.
    assert collega(archivio, tmp_path / "n.sqlite")["collegati"] == 0

    from web.services.gazzetta_runtime import testo_dell_atto

    assert testo_dell_atto(archivio, "gu_" + "a" * 24)["source"].startswith("Normattiva, testo originario")
