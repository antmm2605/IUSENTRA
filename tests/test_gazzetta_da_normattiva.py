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
    assert {k: esito[k] for k in ("candidati", "collegati", "non_in_biblioteca", "numero_discorde")} == \
        {"candidati": 3, "collegati": 1, "non_in_biblioteca": 1, "numero_discorde": 1}
    assert esito["indice_completo"] and not esito["tempo_scaduto"] and esito["edizioni_nuove"] == 3
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


def _archivio_con_atto(tmp_path, codice="26G00222", numero="203", data_atto="2026-10-30"):
    archivio = ArchivioGazzetta(tmp_path / "gu.sqlite")
    archivio.salva_fascicolo({"serie": "SG", "numero": "260", "data": "2026-11-09", "url_sommario": "u", "letto_il": "x"},
                             [_atto("gu_" + "a" * 24, codice, numero, data_atto, "LEGGE 30 ottobre 2026, n. 203")])
    return archivio


def _letture_dei_documenti(percorso):
    """Righe di ``normative_documents`` lette in un giro (dal tracciamento delle istruzioni SQL)."""
    istruzioni = []
    originale = sqlite3.connect

    def connect(*argomenti, **opzioni):
        conn = originale(*argomenti, **opzioni)
        if str(argomenti[0]).startswith("file:") and str(percorso) in str(argomenti[0]):
            conn.set_trace_callback(istruzioni.append)
        return conn

    return istruzioni, connect


def test_secondo_giro_legge_solo_le_edizioni_nuove(tmp_path, monkeypatch):
    """Verifica del 24/11/2026: rileggere tutta la biblioteca a ogni giro richiedeva 35 minuti su disco lento."""
    import pct.gazzetta.da_normattiva as modulo

    archivio = _archivio_con_atto(tmp_path, codice="26G00300", numero="1")
    _normattiva(tmp_path / "n.sqlite")
    primo = collega(archivio, tmp_path / "n.sqlite")
    assert primo["edizioni_nuove"] == 3 and primo["indice_completo"] and primo["collegati"] == 0
    # Arriva in biblioteca l'atto atteso: il giro dopo legge solo la riga nuova e lo collega.
    conn = sqlite3.connect(tmp_path / "n.sqlite")
    conn.execute("INSERT INTO normative_documents VALUES (4,'Normattiva','2026-11-12_26G00300_ORIGINALE_V0.xml','1',"
                 "'2026-10-30','urn:nir:stato:legge:2026-10-30;1','2026-11-12')")
    conn.execute("INSERT INTO normative_articles VALUES (5, 4, '1', 'Art. 1. Nuovo atto.')")
    conn.commit()
    conn.close()
    istruzioni, connect = _letture_dei_documenti(tmp_path / "n.sqlite")
    monkeypatch.setattr(modulo.sqlite3, "connect", connect)
    secondo = collega(archivio, tmp_path / "n.sqlite")
    assert secondo["edizioni_nuove"] == 1 and secondo["collegati"] == 1 and not secondo["indice_ricostruito"]
    scansioni = [sql for sql in istruzioni if "FROM normative_documents WHERE id >" in sql]
    # Riparte dopo l'ultima edizione letta (3), mai dall'inizio della biblioteca.
    assert scansioni and "id > 3" in scansioni[0] and not any("id > 0" in sql for sql in scansioni), scansioni


def test_tempo_massimo_conserva_il_cursore_e_riprende(tmp_path):
    archivio = _archivio_con_atto(tmp_path)
    _normattiva(tmp_path / "n.sqlite")
    passi = iter([0.0, 0.0])  # orologio: partenza, primo lotto; poi 10 s, oltre la scadenza
    esito = collega(archivio, tmp_path / "n.sqlite", tempo_massimo=5.0, lotto=1, orologio=lambda: next(passi, 10.0))
    assert esito["edizioni_nuove"] == 1 and not esito["indice_completo"] and esito["tempo_scaduto"]
    with sqlite3.connect(tmp_path / "gu.sqlite") as gu:
        assert gu.execute("SELECT ultimo_id FROM normattiva_cursore").fetchone()[0] == 1
    ripresa = collega(archivio, tmp_path / "n.sqlite")
    assert ripresa["edizioni_nuove"] == 2 and ripresa["indice_completo"] and ripresa["collegati"] == 1


def _biblioteca_ricostruita(percorso):
    """Una biblioteca nuova con gli stessi identificativi ma edizioni diverse: l'id 3 è un altro atto."""
    percorso.unlink()
    _normattiva(percorso)
    with sqlite3.connect(percorso) as conn:
        conn.execute("UPDATE normative_documents SET xml_entry='2026-11-12_26G00300_ORIGINALE_V0.xml', numero='1', "
                     "data_atto='2026-10-30', urn='urn:nir:stato:legge:2026-10-30;1', redazione_id='2026-11-12' WHERE id=3")
        conn.execute("UPDATE normative_articles SET article_text='Art. 1. Nuovo atto.' WHERE document_id=3")


def test_biblioteca_sostituita_ricostruisce_l_indice(tmp_path):
    archivio = _archivio_con_atto(tmp_path, codice="26G00300", numero="1")
    _normattiva(tmp_path / "n.sqlite")
    collega(archivio, tmp_path / "n.sqlite")
    _biblioteca_ricostruita(tmp_path / "n.sqlite")  # file nuovo, stessi identificativi, edizioni diverse
    esito = collega(archivio, tmp_path / "n.sqlite")
    assert esito["indice_ricostruito"] and esito["edizioni_nuove"] == 3 and esito["collegati"] == 1


def test_biblioteca_sostituita_con_lo_stesso_inode_ricostruisce_l_indice(tmp_path, monkeypatch):
    """CI del 25/11/2026: su ext4 il file ricreato riprende l'inode di quello cancellato; decide l'impronta."""
    import pct.gazzetta.da_normattiva as modulo

    monkeypatch.setattr(modulo, "_identita_biblioteca", lambda percorso: f"{percorso}|inode-riusato")
    archivio = _archivio_con_atto(tmp_path, codice="26G00300", numero="1")
    _normattiva(tmp_path / "n.sqlite")
    assert collega(archivio, tmp_path / "n.sqlite")["collegati"] == 0
    _biblioteca_ricostruita(tmp_path / "n.sqlite")
    esito = collega(archivio, tmp_path / "n.sqlite")
    assert esito["indice_ricostruito"] and esito["edizioni_nuove"] == 3 and esito["collegati"] == 1
    # La stessa biblioteca che si allunga non riparte da capo.
    with sqlite3.connect(tmp_path / "n.sqlite") as conn:
        conn.execute("INSERT INTO normative_documents VALUES (4,'Normattiva','2026-11-13_26G00301_ORIGINALE_V0.xml','2',"
                     "'2026-10-31','urn:nir:stato:legge:2026-10-31;2','2026-11-13')")
    ancora = collega(archivio, tmp_path / "n.sqlite")
    assert not ancora["indice_ricostruito"] and ancora["edizioni_nuove"] == 1


def test_cursore_senza_impronta_resta_valido(tmp_path):
    """Un archivio con il cursore scritto prima dell'impronta non si ricostruisce per questo."""
    archivio = _archivio_con_atto(tmp_path, codice="26G00300", numero="1")
    _normattiva(tmp_path / "n.sqlite")
    collega(archivio, tmp_path / "n.sqlite")
    with sqlite3.connect(tmp_path / "gu.sqlite") as gu:
        identita, ultimo, aggiornato = gu.execute(
            "SELECT biblioteca, ultimo_id, aggiornato_il FROM normattiva_cursore WHERE chiave='normattiva'"
        ).fetchone()
        gu.execute("INSERT OR REPLACE INTO normattiva_cursore VALUES ('normattiva', ?, ?, ?)",
                   (identita.rsplit("|", 1)[0], ultimo, aggiornato))
    esito = collega(archivio, tmp_path / "n.sqlite")
    assert not esito["indice_ricostruito"] and esito["edizioni_nuove"] == 0
