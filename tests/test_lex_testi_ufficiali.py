"""Lex: testo di articoli e sentenze precise dagli archivi ufficiali locali, senza inventare."""

from __future__ import annotations

import sqlite3

import pytest

from lex.normativa.normattiva_importer import ensure_schema
from lex.risposte_certe import risposta_certa
from lex.testi_ufficiali import CODICI, chiave_articolo, collegamento_normattiva, riconosci_articolo, riconosci_sentenza, testo_articolo as leggi_testo_articolo, trova_sentenza


@pytest.mark.parametrize("query,code", [
    ("ART 327 PROCEDURA CIVILE", "cpc"),
    ("art. 327 procedura penale", "cpp"),
    ("articolo 325 codice procedura civile", "cpc"),
    ("art 327 codice procedura penale", "cpp"),
])
def test_denominazioni_brevi_identificano_il_codice(query, code):
    richiesta = riconosci_articolo(query)
    assert richiesta is not None
    assert richiesta.urn == next(c.urn for c in CODICI if c.chiave == code)


@pytest.mark.parametrize("code,annex", [
    ("cpc", ":1"), ("cc", ":2"), ("cp", ":1"),
    ("disp_att_cpc", ":1"), ("disp_att_cpp", ":1"),
    ("cpp", ""), ("cost", ""),
])
def test_link_articolo_usa_il_corpo_corretto(code, annex):
    urn = next(c.urn for c in CODICI if c.chiave == code)
    assert collegamento_normattiva(urn, "1").endswith(urn + annex + "~art1")
    assert collegamento_normattiva(urn).endswith(urn)
    if annex:
        assert collegamento_normattiva(urn + annex, "1").endswith(urn + annex + "~art1")


def test_alias_non_trasforma_domanda_interpretativa_in_testo():
    assert riconosci_articolo("come si applica art 327 procedura civile al mio caso") is None
    assert riconosci_articolo("art 327 procedura sconosciuta") is None


def test_cpp_tipo_atto_equivalente_conserva_identita_completa(tmp_path):
    path = tmp_path / "codici.sqlite"
    conn = sqlite3.connect(path)
    ensure_schema(conn)
    correct_urn = "urn:nir:stato:decreto.del.presidente.della.repubblica:1988-09-22;447"
    document_ids = []
    for urn in [correct_urn, correct_urn + "0", correct_urn.replace("1988-09-22", "1988-09-23")]:
        doc_id = conn.execute(
            "INSERT INTO normative_documents (collection_name,urn,titolo) VALUES (?,?,?)",
            ("Codici", urn, "Codice di procedura penale"),
        ).lastrowid
        conn.execute("INSERT INTO normative_articles (document_id,article_number,article_text) VALUES (?,?,?)",
                     (doc_id, "327", "Art. 327. Direzione delle indagini preliminari. Testo controllato."))
        document_ids.append(doc_id)
    conn.commit()
    conn.close()
    request = riconosci_articolo("ART 327 PROCEDURA PENALE")
    found = leggi_testo_articolo(path, request)
    assert found["urn"] == correct_urn
    assert leggi_testo_articolo(path, request, document_id=document_ids[0])["urn"] == correct_urn
    assert leggi_testo_articolo(path, request, document_id=document_ids[1]) is None
    assert leggi_testo_articolo(path, request, document_id=document_ids[2]) is None
    assert collegamento_normattiva(found["urn"], "327") == (
        "https://www.normattiva.it/uri-res/N2Ls?urn:nir:presidente.repubblica:decreto:1988-09-22;447~art327"
    )


def _archivio(tmp_path):
    percorso = tmp_path / "normattiva.sqlite"
    conn = sqlite3.connect(percorso)
    ensure_schema(conn)
    doc_cc = conn.execute(
        "INSERT INTO normative_documents (collection_name, urn, titolo, vigenza, imported_at) VALUES (?,?,?,?,?)",
        ("Codici", "urn:nir:stato:regio.decreto:1942-03-16;262", "Codice civile", "vigente", "2026-09-20 23:10:00"),
    ).lastrowid
    righe = [
        (doc_cc, "Art. 1.", "Art. 1. Indicazione delle fonti. Sono fonti del diritto: 1) le leggi; 2) i regolamenti."),
        (doc_cc, "Art. 1.", "Art. 1. Capacita' giuridica. La capacita' giuridica si acquista dal momento della nascita."),
        (doc_cc, "Art. 2043.", "Art. 2043. Risarcimento per fatto illecito. Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, obbliga colui che ha commesso il fatto a risarcire il danno."),
    ]
    conn.executemany("INSERT INTO normative_articles (document_id, article_number, article_text) VALUES (?,?,?)", righe)
    doc_l = conn.execute(
        "INSERT INTO normative_documents (collection_name, urn, titolo, imported_at) VALUES (?,?,?,?)",
        ("Leggi", "urn:nir:stato:legge:1994-01-21;53", "Legge 21 gennaio 1994, n. 53", "2026-09-20 23:10:00"),
    ).lastrowid
    conn.execute(
        "INSERT INTO normative_articles (document_id, article_number, article_text) VALUES (?,?,?)",
        (doc_l, "Art. 3 bis.", "Art. 3-bis. 1. La notificazione con modalita' telematica si esegue a mezzo di posta elettronica certificata."),
    )
    # Una legge con numero simile non deve essere confusa.
    doc_x = conn.execute(
        "INSERT INTO normative_documents (collection_name, urn, titolo) VALUES (?,?,?)",
        ("Leggi", "urn:nir:stato:legge:1994-02-01;530", "Legge 530/1994"),
    ).lastrowid
    conn.execute("INSERT INTO normative_articles (document_id, article_number, article_text) VALUES (?,?,?)", (doc_x, "Art. 3 bis.", "Art. 3-bis. Testo di un'altra legge."))
    conn.commit()
    conn.close()
    return str(percorso)


def test_riconoscimento():
    assert chiave_articolo("Art. 3 bis.") == "3bis" and chiave_articolo("Art. 2043.") == "2043"
    assert riconosci_articolo("Qual è il testo dell'art. 2043 c.c.?").etichetta_atto == "codice civile"
    assert riconosci_articolo("cosa prevede l'art. 171-ter c.p.c.").chiave == "171ter"
    assert riconosci_articolo("come si applica l'art. 2043 c.c. a un sinistro") is None
    assert riconosci_articolo("art. 3-bis L. 53/1994").urn_parti == ("stato:legge", "1994", "53")
    s = riconosci_sentenza("Cass. n. 12345/2023")
    assert (s.organo, s.numero, s.anno) == ("cassazione", "12345", "2023")
    assert riconosci_sentenza("art. 3 l. 53/1994") is None


def test_articolo_dal_archivio_verbatim(tmp_path):
    db = _archivio(tmp_path)
    esito = risposta_certa("Riportami il testo dell'art. 2043 c.c.", normattiva_db=db)
    assert esito is not None and esito.tipo == "testo_articolo"
    assert "Qualunque fatto doloso o colposo" in esito.testo
    assert "importato il 20/09/2026" in esito.testo
    assert esito.fonti[0]["url"] == "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043"
    # Art. 1 c.c.: l'articolo del codice, non quello delle preleggi.
    primo = risposta_certa("testo art. 1 c.c.", normattiva_db=db)
    assert "Capacita' giuridica" in primo.testo and "fonti del diritto" not in primo.testo


def test_articolo_di_legge_con_numero_esatto(tmp_path):
    db = _archivio(tmp_path)
    esito = risposta_certa("cosa dice l'art. 3-bis della legge 53/1994?", normattiva_db=db)
    assert "posta elettronica certificata" in esito.testo
    assert "altra legge" not in esito.testo
    assert esito.fonti[0]["url"].endswith("urn:nir:stato:legge:1994-01-21;53~art3bis")


def test_bound_document_ids_preserve_civil_code_and_act_identity(tmp_path):
    from lex.testi_ufficiali import testo_articolo

    db = _archivio(tmp_path)
    request = riconosci_articolo("testo art. 1 c.c.")
    result = testo_articolo(db, request, document_id=1, article_id=1)
    assert "Capacita' giuridica" in result["testo"] and "fonti del diritto" not in result["testo"]
    assert testo_articolo(db, request, document_id=2, article_id=4) is None
    law = riconosci_articolo("testo art. 3-bis della legge 53/1994")
    assert "posta elettronica certificata" in testo_articolo(db, law, document_id=2, article_id=4)["testo"]
    assert testo_articolo(db, law, document_id=3, article_id=5) is None


def test_articolo_assente_nessuna_invenzione(tmp_path):
    db = _archivio(tmp_path)
    esito = risposta_certa("testo dell'art. 2051 c.c.", normattiva_db=db)
    assert esito.tipo == "testo_articolo_assente"
    assert "non ricostruisco a memoria" in esito.testo
    assert "~art2051" in esito.fonti[0]["url"]
    senza_archivio = risposta_certa("testo dell'art. 2043 c.c.", normattiva_db=str(tmp_path / "manca.sqlite"))
    assert senza_archivio.tipo == "testo_articolo_assente"


def _sentenze():
    return [
        {
            "titolo": "Cassazione civile, sez. III, ordinanza n. 12345/2023",
            "organo_giudicante": "Corte di cassazione",
            "numero_provvedimento": "12345/2023",
            "data_deposito": "2023-05-04",
            "massima": "Il custode risponde del danno cagionato dalla cosa salvo il caso fortuito.",
            "url_pagina_ufficiale": "https://www.italgiure.giustizia.it/xway/application/nif/clean/hc.dll?verbo=attach",
            "fonte_ufficiale_confermata": True,
        },
        {
            "titolo": "Corte costituzionale n. 75/2019",
            "organo_giudicante": "Corte costituzionale",
            "numero_provvedimento": "75/2019",
            "principio_diritto": "Notifica telematica perfezionata per il notificante al momento della ricevuta di accettazione.",
            "url_pagina_ufficiale": "https://www.cortecostituzionale.it/actionSchedaPronuncia.do?anno=2019&numero=75",
        },
    ]


def test_sentenza_precisa_dall_archivio():
    esito = risposta_certa("Cosa dice Cass. n. 12345/2023?", sentenze=_sentenze)
    assert esito.tipo == "sentenza"
    assert "Il custode risponde" in esito.testo and "italgiure" in esito.testo
    assert "non ancora confermata" not in esito.testo
    cost = risposta_certa("sentenza Corte costituzionale n. 75 del 2019", sentenze=_sentenze)
    assert "ricevuta di accettazione" in cost.testo and "non ancora confermata" in cost.testo


def test_sentenza_assente_o_organo_diverso():
    assert trova_sentenza(_sentenze(), riconosci_sentenza("Cass. n. 75/2019")) is None
    esito = risposta_certa("Cass. n. 999/2020 cosa ha deciso?", sentenze=_sentenze)
    assert esito.tipo == "sentenza_assente" and "non ne riporto" in esito.testo
