from pathlib import Path

from pct.giurisprudenza import GestioneGiurisprudenza
from pct.giurisprudenza_corpus import (
    GestioneCorpusGiurisprudenza,
    derive_corpus_db_path,
)


def test_corpus_giurisprudenza_salva_sentenza_professionale_con_relazioni(tmp_path: Path):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))

    saved = corpus.salva_sentenza(
        {
            "fonte": {
                "codice": "cassazione",
                "nome": "Corte di Cassazione",
                "tipo_fonte": "ufficiale",
                "ente": "Corte di Cassazione",
                "url_home": "https://www.cortedicassazione.it/",
            },
            "ecli": "ECLI:IT:CASS:2026:1234",
            "numero_sentenza": "1234",
            "anno_sentenza": 2026,
            "organo_giudicante": "Corte di Cassazione",
            "sezione": "Sez. III",
            "data_decisione": "2026-04-08",
            "data_deposito": "2026-04-10",
            "area_diritto": "Civile",
            "materia_principale": "Responsabilita civile",
            "sottomateria_principale": "Responsabilita medica",
            "tipo_provvedimento": "sentenza",
            "titolo": "Cassazione su consenso informato",
            "abstract": "Pronuncia su onere probatorio del consenso informato.",
            "principio_sintetico": "Il consenso informato va provato in modo specifico.",
            "massima_ufficiale": "La prova del consenso informato richiede allegazione puntuale.",
            "testo_integrale": "Testo integrale della pronuncia.",
            "stato_verifica": "verificata",
            "fonte_ufficiale_confermata": True,
            "pdf_ufficiale_presente": True,
            "url_pagina_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026",
            "url_pdf_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026.pdf",
            "documenti": [
                {
                    "tipo_documento": "pdf_ufficiale",
                    "titolo": "PDF ufficiale",
                    "url_origine": "https://www.cortedicassazione.it/sentenza-1234-2026.pdf",
                    "mime_type": "application/pdf",
                    "ufficiale": True,
                    "valido": True,
                }
            ],
            "massime": [
                {
                    "testo": "La prova del consenso informato richiede allegazione puntuale.",
                    "ufficiale": True,
                    "stato_verifica": "verificata",
                    "principale": True,
                }
            ],
            "principi_diritto": [
                {
                    "testo": "Il consenso informato va provato in modo specifico.",
                    "formulazione_breve": "Onere probatorio specifico.",
                    "ufficiale": True,
                    "tema": "consenso informato",
                    "sotto_tema": "onere della prova",
                    "principale": True,
                }
            ],
            "norme": [
                {
                    "tipo_norma": "codice",
                    "sigla": "c.c.",
                    "articolo": "2043",
                    "testo_riferimento": "Art. 2043 c.c.",
                    "tipo_richiamo": "interpretata",
                    "primaria": True,
                }
            ],
            "precedenti": [
                {
                    "riferimento_testuale": "Cass. 999/2024",
                    "organo_giudicante": "Corte di Cassazione",
                    "numero_sentenza": "999",
                    "anno_sentenza": 2024,
                    "tipo_relazione": "conforme",
                    "verificata": True,
                }
            ],
            "verifiche": [
                {
                    "tipo_verifica": "esistenza_url",
                    "esito": "ok",
                    "dettaglio": "Pagina ufficiale raggiungibile",
                }
            ],
        }
    )

    assert saved["ecli"] == "ECLI:IT:CASS:2026:1234"
    assert saved["fonte_codice"] == "cassazione"
    assert len(saved["documenti"]) == 1
    assert len(saved["massime"]) == 1
    assert len(saved["principi_diritto"]) == 1
    assert len(saved["norme"]) == 1
    assert len(saved["precedenti"]) == 1
    assert corpus.can_cite_sentenza(saved) is True
    assert corpus.can_offer_pdf(saved) is True


def test_corpus_giurisprudenza_blocca_citazione_e_pdf_se_non_verificati(tmp_path: Path):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))

    saved = corpus.salva_sentenza(
        {
            "fonte": {
                "codice": "import_manuale",
                "nome": "Import manuale",
                "tipo_fonte": "import_manuale",
            },
            "titolo": "Pronuncia tematica non verificata",
            "organo_giudicante": "Organo non confermato",
            "tipo_provvedimento": "sentenza",
            "stato_verifica": "da_verificare",
            "massima_ufficiale": "Massima redazionale non verificata.",
        }
    )

    assert corpus.can_cite_sentenza(saved) is False
    assert corpus.can_offer_pdf(saved) is False


def test_gestione_giurisprudenza_sincronizza_il_record_nel_corpus_professionale(tmp_path: Path):
    json_path = tmp_path / "giurisprudenza.json"
    gestore = GestioneGiurisprudenza(str(json_path))

    saved = gestore.salva(
        {
            "source_system": "cassazione",
            "titolo": "Cassazione su accesso difensivo",
            "organo_giudicante": "Corte di Cassazione",
            "sezione": "Sez. II",
            "numero_provvedimento": "456/2026",
            "data_deposito": "2026-04-11",
            "area": "Civile",
            "branca": "Contratti",
            "sottobranca": "Accesso difensivo",
            "massima": "L'accesso difensivo va valutato in concreto.",
            "principio_diritto": "Serve un collegamento specifico tra documento richiesto e difesa.",
            "stato_verifica_fonte": "verificata",
            "fonte_ufficiale_confermata": True,
            "url_pagina_ufficiale": "https://www.cortedicassazione.it/sentenza-456-2026",
            "url_pdf_ufficiale": "https://www.cortedicassazione.it/sentenza-456-2026.pdf",
            "pdf_ufficiale_presente": True,
            "precedenti_citati": ["Cass. 120/2024"],
            "norme_citate": ["Art. 24 Cost."],
            "uso_nel_software": "precedente forte",
        }
    )

    corpus = GestioneCorpusGiurisprudenza(derive_corpus_db_path(str(json_path)))
    hits = corpus.cerca_sentenze(q="accesso")
    stats = gestore.storage_stats()

    assert saved["id"]
    assert len(hits) == 1
    full = corpus.get_sentenza(hits[0]["id"])
    assert full is not None
    assert full["titolo"] == "Cassazione su accesso difensivo"
    assert corpus.can_cite_sentenza(full) is True
    assert corpus.can_offer_pdf(full) is True
    assert stats["corpus_sentenze"] >= 1
    assert stats["corpus_documenti"] >= 1
