"""Integrazione delle leggi ordinarie essenziali nell'archivio Normattiva (2.436.10).

Normattiva Open Data non ha una collezione di leggi ordinarie: Costituzione, l. 241/1990, l. 53/1994,
l. 742/1969 ecc. mancavano dall'archivio. ``lex/normativa/integrazione_leggi.py`` le inserisce dal file
``lex/normativa/integrazioni/leggi_essenziali.jsonl`` nello stesso formato degli altri atti.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from lex.normativa.integrazione_leggi import (
    COLLEZIONE,
    FILE_PREDEFINITO,
    documento_da_righe,
    impronta_atto,
    integra,
    leggi_jsonl,
    verifica,
)
from lex.retrieval.normativa import etichetta_fonte_normattiva
from lex.ricerca_giuridica.ibrida import cerca_normattiva_indicizzata
from tests.lex_fonti_banco.valutazione import costruisci_db

os.environ.setdefault("LEX_RICERCA_SEMANTICA", "0")

RIGHE = [
    {"chiave": "legge_742_1969", "atto": "l. 742/1969", "articolo": "1", "rubrica": "",
     "testo": "Art. 1. Il decorso dei termini processuali relativi alle giurisdizioni ordinarie ed a quelle amministrative "
              "e' sospeso di diritto dal 1° al 31 agosto di ciascun anno, e riprende a decorrere dalla fine del periodo di sospensione.",
     "titolo_atto": "Sospensione dei termini processuali nel periodo feriale.", "data_atto": "1969-10-07",
     "urn": "urn:nir:stato:legge:1969-10-07;742", "fonte_testo": "prova", "url": ""},
    {"chiave": "legge_742_1969", "atto": "l. 742/1969", "articolo": "3", "rubrica": "",
     "testo": "Art. 3. In materia civile, l'articolo 1 non si applica alle cause ed ai procedimenti indicati nell'articolo 92 "
              "dell'ordinamento giudiziario, nonche' alle controversie di lavoro e previdenziali.",
     "titolo_atto": "Sospensione dei termini processuali nel periodo feriale.", "data_atto": "1969-10-07",
     "urn": "urn:nir:stato:legge:1969-10-07;742", "fonte_testo": "prova", "url": ""},
    {"chiave": "costituzione", "atto": "Costituzione", "articolo": "24", "rubrica": "",
     "testo": "Art. 24. Tutti possono agire in giudizio per la tutela dei propri diritti e interessi legittimi. "
              "La difesa e' diritto inviolabile in ogni stato e grado del procedimento.",
     "titolo_atto": "Costituzione della Repubblica Italiana.", "data_atto": "1947-12-27",
     "urn": "urn:nir:stato:costituzione:1947-12-27", "fonte_testo": "prova", "url": ""},
]


def _scrivi(tmp_path: Path, righe: list[dict]) -> Path:
    f = tmp_path / "leggi.jsonl"
    f.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in righe) + "\n", encoding="utf-8")
    return f


def _db(tmp_path: Path) -> Path:
    return costruisci_db(tmp_path / "normattiva.sqlite")


def test_documento_da_righe_ricava_tipo_numero_e_articoli():
    doc = documento_da_righe("legge_742_1969", RIGHE[:2])
    assert doc.tipo_atto == "Legge" and doc.numero == "742" and doc.data_atto == "1969-10-07"
    assert doc.vigenza == "VIGENTE" and doc.collection_name == COLLEZIONE and doc.is_relevant
    assert [a.article_number for a in doc.articles] == ["Art. 1.", "Art. 3."]
    cost = documento_da_righe("costituzione", RIGHE[2:])
    assert cost.tipo_atto == "Costituzione" and cost.numero is None


def test_integra_inserisce_indicizza_e_la_ricerca_trova_la_legge(tmp_path):
    db = _db(tmp_path)
    esito = integra(db, jsonl=_scrivi(tmp_path, RIGHE))
    assert esito.atti_inseriti == 2 and esito.articoli_inseriti == 3 and esito.fts_indicizzati == 3
    conn = sqlite3.connect(str(db))
    info = conn.execute(
        "SELECT atto_numero, atto_anno, articolo, vigenza, identita FROM normative_fts_info "
        "WHERE atto_numero = '742' ORDER BY articolo").fetchall()
    assert info == [("742", "1969", "1", "VIGENTE", "atto:742/1969"), ("742", "1969", "3", "VIGENTE", "atto:742/1969")]
    cost = conn.execute("SELECT codice, articolo FROM normative_fts_info WHERE codice = 'costituzione'").fetchall()
    assert cost == [("costituzione", "24")]
    conn.close()
    righe = cerca_normattiva_indicizzata("sospensione feriale dei termini processuali dal 1 al 31 agosto", db, limite=3)
    assert righe and righe[0]["metadata"]["article_number"] == "Art. 1." and "742" in str(righe[0]["metadata"]["numero"])
    righe = cerca_normattiva_indicizzata("art. 24 cost. diritto di difesa", db, limite=3)
    assert righe and righe[0]["metadata"]["article_number"] == "Art. 24." and righe[0]["riferimento_esatto"]


def test_integra_e_idempotente_e_sostituisce_il_testo_cambiato(tmp_path):
    db = _db(tmp_path)
    file = _scrivi(tmp_path, RIGHE)
    integra(db, jsonl=file)
    secondo = integra(db, jsonl=file)
    assert secondo.atti_gia_presenti == 2 and secondo.atti_inseriti == 0 and secondo.chunk_inseriti == 0

    modificate = [dict(r) for r in RIGHE]
    modificate[0]["testo"] = modificate[0]["testo"].replace("31 agosto", "15 settembre")
    terzo = integra(db, jsonl=_scrivi(tmp_path, modificate))
    assert terzo.atti_sostituiti == 1 and terzo.atti_gia_presenti == 1
    conn = sqlite3.connect(str(db))
    documenti = conn.execute(
        "SELECT COUNT(*) FROM normative_documents WHERE urn = ?", ("urn:nir:stato:legge:1969-10-07;742",)).fetchone()[0]
    chunk = conn.execute(
        "SELECT COUNT(*) FROM normative_chunks c JOIN normative_documents d ON d.id = c.document_id WHERE d.urn = ?",
        ("urn:nir:stato:legge:1969-10-07;742",)).fetchone()[0]
    orfani = conn.execute(
        "SELECT COUNT(*) FROM normative_fts_info i WHERE NOT EXISTS (SELECT 1 FROM normative_chunks c WHERE c.id = i.chunk_id)"
    ).fetchone()[0]
    conn.close()
    assert documenti == 1 and chunk == 2 and orfani == 0
    righe = cerca_normattiva_indicizzata("sospensione dei termini 15 settembre", db, limite=2)
    assert righe and "15 settembre" in righe[0]["testo"]


def test_integra_non_tocca_un_archivio_originale(tmp_path):
    db = _db(tmp_path)
    esito = integra(db, jsonl=_scrivi(tmp_path, RIGHE), vigenza_archivio="ORIGINALE")
    assert esito.atti_letti == 0 and esito.atti_inseriti == 0


def test_file_jsonl_del_repository_e_coerente():
    assert FILE_PREDEFINITO.exists(), "manca lex/normativa/integrazioni/leggi_essenziali.jsonl"
    gruppi = leggi_jsonl(FILE_PREDEFINITO)
    attesi = {"costituzione", "legge_241_1990", "legge_53_1994", "legge_742_1969", "legge_689_1981", "legge_898_1970",
              "legge_300_1970", "legge_604_1966", "legge_392_1978", "legge_431_1998", "legge_247_2012", "legge_24_2017",
              "dl_132_2014", "legge_890_1982"}
    assert attesi <= set(gruppi), sorted(attesi - set(gruppi))
    assert len(gruppi["costituzione"]) == 139
    for chiave, righe in gruppi.items():
        assert len({r["articolo"] for r in righe}) == len(righe), f"{chiave}: articoli duplicati"
        assert all(r["testo"].startswith("Art.") for r in righe), chiave
        assert len({r["urn"] for r in righe}) == 1, chiave
    art_742 = {r["articolo"]: r["testo"] for r in gruppi["legge_742_1969"]}
    assert "31 agosto" in art_742["1"]
    art_53 = {r["articolo"]: r["testo"] for r in gruppi["legge_53_1994"]}
    assert "ricevuta di accettazione" in art_53["3bis"] and "avvenuta consegna" in art_53["3bis"]
    assert impronta_atto(gruppi["legge_742_1969"]) == impronta_atto(list(gruppi["legge_742_1969"]))


def test_etichetta_fonte_breve_per_codici_e_atti():
    assert etichetta_fonte_normattiva({"titolo": "Approvazione del testo del Codice civile. (042U0262)", "data": "1942-03-16",
                                       "metadata": {"numero": "262", "data_atto": "1942-03-16"}}) == "Codice civile"
    assert etichetta_fonte_normattiva({"titolo": "Costituzione della Repubblica Italiana.", "data": "1947-12-27",
                                       "metadata": {"numero": None}}) == "Costituzione"
    etichetta = etichetta_fonte_normattiva({
        "titolo": "Facolta' di notificazioni di atti civili, amministrativi e stragiudiziali per gli avvocati e procuratori legali.",
        "data": "1994-01-21", "url_origine": "urn:nir:stato:legge:1994-01-21;53", "metadata": {"numero": "53"}})
    assert etichetta.startswith("l. 53/1994, Facolta' di notificazioni") and etichetta.endswith("…")
    assert etichetta_fonte_normattiva({"titolo": "Nuovo codice della strada.", "data": "1992-04-30",
                                       "metadata": {"numero": "285", "data_atto": "1992-04-30"}}) == "Codice della strada"


def test_verifica_elenca_gli_atti(tmp_path):
    db = _db(tmp_path)
    file = _scrivi(tmp_path, RIGHE)
    integra(db, jsonl=file)
    righe = verifica(db, jsonl=file)
    assert any("l. 742/1969" in r and "2 (nel file: 2)" in r for r in righe)
    assert any("ricerca" in r for r in righe)


@pytest.mark.parametrize("campo", ["chiave", "testo", "urn"])
def test_file_senza_campo_obbligatorio_viene_rifiutato(tmp_path, campo):
    riga = dict(RIGHE[0]); riga[campo] = ""
    file = _scrivi(tmp_path, [riga])
    with pytest.raises(ValueError):
        leggi_jsonl(file)
