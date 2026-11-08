"""Norma citata nella Ricerca legale: estremi riconosciuti, articolo e comma letti dall'archivio, atto assente detto."""

from __future__ import annotations

import sqlite3

from web.services.ricerca_legale_norma_citata import estremi, in_cima, norma_citata
from web.services.ricerca_legale_norma_citata import testo_del_comma as comma_dal_testo

_ART1_B = ("1 101. Per ciascuna iscrizione in graduatoria si procede. 120. Continuano ad applicarsi gli articoli. "
           "121. Al fine di sostenere la formazione continua dei docenti e' istituita la Carta elettronica per l'aggiornamento "
           "e la formazione del docente di ruolo. Per le finalita' di cui al comma 121. si provvede. 122. Con decreto sono definiti i criteri.")


def _archivio(tmp_path):
    db = tmp_path / "normattiva.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE normative_documents (id INTEGER PRIMARY KEY, numero TEXT, data_atto TEXT, titolo TEXT, vigenza TEXT, xml_entry TEXT, zip_path TEXT);
        CREATE TABLE normative_articles (id INTEGER PRIMARY KEY, document_id INTEGER, article_number TEXT, article_text TEXT, article_key TEXT);
        CREATE TABLE normative_chunks (id INTEGER PRIMARY KEY, article_id INTEGER, chunk_key TEXT, chunk_text TEXT);
        """)
        conn.execute("INSERT INTO normative_documents VALUES (1,'107','2015-07-13','Riforma del sistema nazionale di istruzione','VIGENTE',"
                     "'LEGGE_20150713_107/2015-07-15_15G00122_VIGENZA_2026-02-22_V0.xml','')")
        conn.execute("INSERT INTO normative_documents VALUES (2,'107','2015-03-02','Altro atto','VIGENTE',"
                     "'DECRETO LEGISLATIVO_20150302_107/x_VIGENZA_2025-01-01_V0.xml','')")
        conn.execute("INSERT INTO normative_articles VALUES (10,1,'Art. 1 (commi 1-50).','1 La Camera ha approvato. 1. Primo comma.','k1')")
        conn.execute("INSERT INTO normative_articles VALUES (11,1,'Art. 1 (commi 101-150).',?,'k2')", (_ART1_B,))
        conn.execute("INSERT INTO normative_chunks VALUES (1,11,'normattiva:x:art2:chunk1',?)", (_ART1_B[:60],))
        conn.execute("INSERT INTO normative_chunks VALUES (2,11,'normattiva:x:art2:chunk2',?)", (_ART1_B[100:],))
    return db


def test_estremi_riconosciuti_in_tutte_le_forme_d_uso():
    for domanda in ("art. 1 comma 121 legge 107/2015", "art. 1, comma 121, L. 107/2015", "art. 1 c. legge 13 luglio 2015, n. 107"):
        e = estremi(domanda)
        assert e and (e["sigla"], e["numero"], e["anno"], e["articolo"]) == ("L.", "107", "2015", "1"), domanda
    assert estremi("art. 52, comma 5, d.lgs. 165/2001")["sigla"] == "D.Lgs."
    assert estremi("art. 2-bis d.l. 18/2020")["articolo"] == "2bis"
    assert estremi("carta elettronica docente legge 107 2015")["parole"] == "carta elettronica docente"
    assert estremi("art. 2043 c.c.") is None and estremi("prescrizione dei crediti di lavoro") is None


def test_comma_dal_numero_al_successivo_senza_confondere_i_rinvii():
    testo = comma_dal_testo(_ART1_B, "121")
    assert testo.startswith("121. Al fine") and testo.endswith("si provvede.")


def test_norma_citata_apre_articolo_e_comma_vigenti(tmp_path):
    scheda = norma_citata(_archivio(tmp_path), estremi("art. 1 comma 121 legge 107/2015"))
    assert scheda["title"].startswith("L. 107/2015 — art. 1, comma 121")
    assert scheda["officialContext"].startswith("121. Al fine")
    assert scheda["sourceHref"].endswith("urn:nir:stato:legge:2015-07-13;107~art1")
    assert "22/02/2026" in scheda["operationalChecks"][0]


def test_senza_articolo_il_comma_si_individua_dalle_parole_e_si_dice(tmp_path):
    scheda = norma_citata(_archivio(tmp_path), estremi("carta elettronica docente legge 107 2015"))
    assert "comma 121" in scheda["title"]
    assert any("individuati dalle parole" in avviso for avviso in scheda["operationalChecks"])


def test_atto_assente_dichiarato_con_collegamento_a_normattiva(tmp_path):
    scheda = norma_citata(_archivio(tmp_path), estremi("art. 2-bis d.l. 18/2020"))
    assert scheda["normaAssente"] and "non presente nell'archivio" in scheda["title"]
    assert scheda["title"].startswith("D.L. 18/2020 — art. 2-bis")
    assert scheda["sourceHref"].endswith("urn:nir:stato:decreto.legge:2020;18~art2bis")


def test_la_norma_citata_va_in_cima_e_non_si_duplica(tmp_path):
    db = _archivio(tmp_path)
    altri = [{"id": "centro-fonti-dpr-115"}, {"id": "normattiva:x:art2:chunk2"}]
    risultato = in_cima(altri, "art. 1 comma 121 legge 107/2015", db=db)
    assert risultato[0]["normaCitata"] and risultato[0]["id"] == "normattiva:x:art2:chunk2"
    assert [r["id"] for r in risultato[1:]] == ["centro-fonti-dpr-115"]
    assert in_cima(altri, "mediazione obbligatoria", db=db) == altri


def test_estremi_dai_campi_della_ricerca(tmp_path):
    e = estremi("", {"atto_tipo": "LEGGE", "atto_numero": "107", "atto_anno": "2015", "articolo": "1", "comma": "121"})
    assert norma_citata(_archivio(tmp_path), e)["officialContext"].startswith("121.")


def test_intestazione_dell_articolo_non_e_il_comma_omonimo():
    from web.services.ricerca_legale_norma_citata import testo_del_comma as comma_testo

    assert comma_testo("Art. 2. 1 Art. 2. Cessioni di beni. Costituiscono cessioni di beni gli atti.", "2") == ""


def _archivio_decreti(tmp_path):
    db = _archivio(tmp_path)
    with sqlite3.connect(db) as conn:
        # Come nell'archivio reale: i decreti ministeriali sono sotto il tipo generico «DECRETO_».
        conn.execute("INSERT INTO normative_documents VALUES (3,'55','2014-03-10','Parametri compensi forensi','VIGENTE',"
                     "'DECRETO_20140310_55/2014-04-02_14G00067_VIGENZA_2025-10-14_V0.xml','')")
        conn.execute("INSERT INTO normative_articles VALUES (30,3,'Art. 4.',?,'k30')",
                     ("1. Il giudice tiene conto dei valori medi, che possono essere aumentati fino al 50 per cento. 2. Altro.",))
        # Stesso numero e anno, date diverse fra i due tipi: gli estremi non individuano un atto solo.
        conn.execute("INSERT INTO normative_documents VALUES (4,'12','2020-01-10','Decreto A','VIGENTE',"
                     "'DECRETO_20200110_12/x_VIGENZA_2025-01-01_V0.xml','')")
        conn.execute("INSERT INTO normative_documents VALUES (5,'12','2020-05-02','Decreto B','VIGENTE',"
                     "'DECRETO MINISTERIALE_20200502_12/x_VIGENZA_2025-01-01_V0.xml','')")
    return db


def test_decreto_ministeriale_si_apre_per_estremi_anche_sotto_il_tipo_generico(tmp_path):
    db = _archivio_decreti(tmp_path)
    scheda = norma_citata(db, estremi("art. 4 comma 1 d.m. 55/2014"))
    assert scheda["title"].startswith("D.M. 55/2014 — art. 4, comma 1")
    assert "fino al 50 per cento" in scheda["officialContext"]
    campi = estremi("", {"atto_tipo": "DECRETO MINISTERIALE", "atto_numero": "55", "atto_anno": "2014", "articolo": "4"})
    assert norma_citata(db, campi)["title"].startswith("D.M. 55/2014 — art. 4")


def test_decreti_omonimi_con_date_diverse_non_si_scelgono(tmp_path):
    assert norma_citata(_archivio_decreti(tmp_path), estremi("art. 1 d.m. 12/2020")) is None
