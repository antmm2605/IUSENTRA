"""Divisione in articoli del testo Normattiva e riallineamento degli archivi gia' importati (2.436.10)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from lex.normativa.articoli_testuali import chiave_numero, dividi_in_articoli, solo_intestazione
from lex.normativa.normattiva_importer import ensure_schema, extract_textual_article_records
from lex.normativa.riallinea_articoli import analizza, riallinea
from lex.ricerca_giuridica.testo import articolo_normalizzato

os.environ.setdefault("LEX_RICERCA_SEMANTICA", "0")

CODICE = (
    "Art. 2316. (Responsabilita' dei soci). I soci accomandatari rispondono illimitatamente. "
    "Art. 2317. (Mancata registrazione). Fino a quando la societa' non e' iscritta nel registro delle imprese, ai rapporti "
    "fra la societa' e i terzi si applicano le disposizioni dell'art. 2297. Gli accomandatari rispondono. "
    "Art. 2318. (Soci accomandatari). I soci accomandatari hanno i diritti e gli obblighi dei soci della societa' in nome collettivo."
)


def test_nessun_taglio_sui_rimandi_interni():
    numeri = [s.numero for s in dividi_in_articoli(CODICE)]
    assert numeri == ["2316", "2317", "2318"]
    art_2317 = dividi_in_articoli(CODICE)[1].testo
    assert art_2317.endswith("Gli accomandatari rispondono.") and "dell'art. 2297" in art_2317


def test_intestazioni_senza_punteggiatura_con_parentesi_e_suffissi_lunghi():
    testo = (
        "Art. 29 Azione di annullamento 1. L'azione di annullamento si propone nel termine di decadenza di sessanta giorni. "
        "Art. 30 Azione di condanna 1. L'azione di condanna puo' essere proposta contestualmente. "
        "Art. 183-ter (Ordinanza di accoglimento della domanda). Il giudice pronuncia ordinanza di accoglimento. "
        "Art. 669-terdecies. (Reclamo contro i provvedimenti cautelari). Contro l'ordinanza e' ammesso reclamo. "
        "Art. 473-bis.14. (Ricorso). La domanda si propone con ricorso al tribunale."
    )
    assert [s.numero for s in dividi_in_articoli(testo)] == ["29", "30", "183-ter", "669-terdecies", "473-bis.14"]


def test_testo_citato_negli_atti_di_modifica_non_diventa_un_articolo():
    testo = ("Art. 3. (Modifiche). 1. Dopo l'articolo 183 e' inserito il seguente: «Art. 183-bis. (Ordinanza). Il giudice "
             "provvede.» Art. 4. (Entrata in vigore). Il presente decreto entra in vigore il giorno successivo.")
    assert [s.numero for s in dividi_in_articoli(testo)] == ["3", "4"]


def test_numero_normalizzato_distingue_i_suffissi_lunghi():
    assert articolo_normalizzato("669-terdecies") == "669terdecies" != articolo_normalizzato("669-ter")
    assert articolo_normalizzato("Art. 473-bis.14.") == "473bis.14"
    assert chiave_numero("Art. 669 terdecies.") == "669terdecies"


def test_importatore_usa_la_nuova_divisione():
    record = extract_textual_article_records(CODICE)
    assert [r.article_number for r in record] == ["Art. 2316.", "Art. 2317.", "Art. 2318."]


def test_solo_intestazione():
    assert solo_intestazione("Art. 29 - Azione di annullamento")
    assert not solo_intestazione("Art. 2043. Qualunque fatto doloso o colposo cagiona un danno ingiusto.")


def _db_con_vecchia_divisione(tmp_path: Path) -> tuple[Path, int]:
    db = tmp_path / "normattiva.sqlite"
    conn = sqlite3.connect(str(db))
    ensure_schema(conn)
    cur = conn.execute(
        "INSERT INTO normative_documents (collection_name, zip_path, xml_entry, tipo_atto, numero, data_atto, titolo, urn, "
        "vigenza, xml_sha256, topics, relevance_score, is_relevant) VALUES ('Codici','z','e','Regio Decreto','1443','1940-10-28',"
        "'Codice di procedura civile.','urn:x','VIGENTE','sha-prova','[]',3,1)")
    doc = int(cur.lastrowid)
    articoli = [
        # troncato su un rimando, con il seguito finito sotto un numero sbagliato
        ("Art. 2317.", "Art. 2317. (Mancata registrazione). Fino all'iscrizione si applicano le disposizioni dell'"),
        ("Art. 2297.", "art. 2297. Gli accomandatari rispondono solidalmente e illimitatamente per le obbligazioni sociali."),
        # articoli fusi nell'articolo base
        ("Art. 669.", "Art. 669. (Procedimento cautelare). Le disposizioni si applicano ai provvedimenti cautelari. "
                      "Art. 669-terdecies. (Reclamo contro i provvedimenti cautelari). Contro l'ordinanza e' ammesso reclamo "
                      "nel termine perentorio di quindici giorni."),
        # nodo con il solo titolo, testo dentro un altro articolo
        ("Art. 29.", "Art. 29 - Azione di annullamento"),
        ("Art. 25.", "Art. 25. Domicilio 1. La parte elegge domicilio. Art. 29 Azione di annullamento 1. L'azione di "
                     "annullamento si propone nel termine di decadenza di sessanta giorni."),
    ]
    for i, (numero, testo) in enumerate(articoli, 1):
        art = conn.execute(
            "INSERT INTO normative_articles (document_id, article_number, article_text, topics, relevance_score, article_key) "
            "VALUES (?,?,?,?,?,?)", (doc, numero, testo, "[]", 1, f"k{i}")).lastrowid
        conn.execute("INSERT INTO normative_chunks (document_id, article_id, chunk_key, chunk_text, metadata_json) VALUES (?,?,?,?,?)",
                     (doc, art, f"c{i}", testo, "{}"))
    conn.commit()
    conn.close()
    return db, doc


def test_riallinea_corregge_e_e_idempotente(tmp_path):
    db, doc = _db_con_vecchia_divisione(tmp_path)
    analisi = riallinea(db, applica=False)
    assert analisi.documenti_con_difetti == 1 and analisi.documenti_riallineati == 0

    esito = riallinea(db)
    assert esito.documenti_riallineati == 1 and esito.documenti_saltati == 0
    conn = sqlite3.connect(str(db))
    articoli = dict(conn.execute("SELECT article_number, article_text FROM normative_articles WHERE document_id = ?", (doc,)))
    chunk = conn.execute("SELECT COUNT(*) FROM normative_chunks WHERE document_id = ?", (doc,)).fetchone()[0]
    conn.close()
    assert set(articoli) == {"Art. 2317.", "Art. 669.", "Art. 669-terdecies.", "Art. 25.", "Art. 29."}
    assert articoli["Art. 2317."].endswith("per le obbligazioni sociali.")
    assert "quindici giorni" in articoli["Art. 669-terdecies."] and "quindici" not in articoli["Art. 669."]
    assert "sessanta giorni" in articoli["Art. 29."] and "sessanta" not in articoli["Art. 25."]
    assert chunk == len(articoli)

    secondo = riallinea(db)
    assert secondo.documenti_con_difetti == 0 and secondo.documenti_riallineati == 0


def test_analizza_non_tocca_documenti_sani():
    articoli = [(1, "Art. 1.", "Art. 1. Il processo si svolge davanti al giudice."),
                (2, "Art. 2.", "Art. 2. Le parti stanno in giudizio con un difensore, salvo l'art. 86.")]
    assert analizza(articoli).segmenti is None and not any(analizza(articoli).difetti.values())
