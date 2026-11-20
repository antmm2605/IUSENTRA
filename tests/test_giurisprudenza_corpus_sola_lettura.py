"""L'archivio giurisprudenza in WAL resta leggibile da una cartella non scrivibile (montaggio in sola lettura).

Difetto del 20/11/2026: con il file di root in WAL, ``mode=ro`` falliva con «attempt to write a readonly database»
e la ricerca FTS restituiva in silenzio zero risultati.
"""
from __future__ import annotations

import os
import sqlite3
import stat

import pytest

from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza


@pytest.mark.skipif(os.geteuid() == 0, reason="root scrive comunque nella cartella")
def test_ricerca_su_archivio_wal_in_cartella_non_scrivibile(tmp_path):
    cartella = tmp_path / "corpus"
    cartella.mkdir()
    db = cartella / "giurisprudenza_corpus.db"
    GestioneCorpusGiurisprudenza(str(db))  # crea lo schema in WAL
    conn = sqlite3.connect(db)
    if True:  # commit e checkpoint espliciti, poi chiusura
        conn.execute("INSERT INTO fonti_giurisprudenza (codice, nome, tipo_fonte) VALUES ('corte_costituzionale', "
                     "'Corte costituzionale', 'ufficiale')")
        conn.execute("INSERT INTO sentenze (fonte_id, uuid_interno, tipo_provvedimento, organo_giudicante, numero_sentenza, "
                     "anno_sentenza, titolo, massima_ufficiale) VALUES (last_insert_rowid(), 'u-49-1990', 'sentenza', "
                     "'Corte costituzionale', '49', '1990', 'Sospensione feriale', "
                     "'La sospensione feriale si applica al termine per impugnare le delibere condominiali')")
        conn.execute("INSERT INTO sentenze_fts (rowid, titolo, massima_ufficiale) VALUES (last_insert_rowid(), "
                     "'Sospensione feriale', 'La sospensione feriale si applica al termine per impugnare le delibere condominiali')")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    for nome in os.listdir(cartella):
        if nome != db.name:
            os.remove(cartella / nome)
    os.chmod(db, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    os.chmod(cartella, stat.S_IRUSR | stat.S_IXUSR)
    try:
        corpus = GestioneCorpusGiurisprudenza(str(db), read_only=True)
        righe = corpus.cerca_sentenze(q="sospensione feriale delibere", limit=5, semantica=False)
        assert [r["numero_sentenza"] for r in righe] == ["49"]
    finally:
        os.chmod(cartella, stat.S_IRWXU)


def test_estremi_con_zeri_iniziali_come_in_sentenzeweb(tmp_path):
    db = tmp_path / "giurisprudenza_corpus.db"
    GestioneCorpusGiurisprudenza(str(db))
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO fonti_giurisprudenza (codice, nome, tipo_fonte) VALUES ('cassazione_sentenzeweb', 'Cassazione', 'ufficiale')")
    conn.execute("INSERT INTO sentenze (fonte_id, uuid_interno, tipo_provvedimento, organo_giudicante, sezione, numero_sentenza, "
                 "anno_sentenza, titolo) VALUES (last_insert_rowid(), 'u-5425-2021', 'sentenza', 'Corte di Cassazione — civile', "
                 "'U', '05425', 2021, 'Sezioni unite')")
    conn.commit()
    conn.close()
    corpus = GestioneCorpusGiurisprudenza(str(db), read_only=True)
    for domanda in ("5425/2021", "05425/2021", "Cass. S.U. n. 5425/2021"):
        righe = corpus.cerca_sentenze(q=domanda, limit=3, semantica=False)
        assert [r["numero_sentenza"] for r in righe] == ["05425"], domanda
