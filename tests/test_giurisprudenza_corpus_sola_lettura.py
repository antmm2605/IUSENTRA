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
