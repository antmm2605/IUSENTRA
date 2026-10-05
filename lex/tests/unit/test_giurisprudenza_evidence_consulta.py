"""Dal corpus giurisprudenziale a quello che vede il modello: EvidenceItem e intestazione della fonte."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import lex.retrieval.giurisprudenza as retrieval_giurisprudenza
from lex.contracts import EvidenceItem
from lex.providers.prompt_budget import evidence_header, format_evidence_item
from lex.retrieval.sources.giurisprudenza import GiurisprudenzaSource
from pct.corte_costituzionale_opendata import componi_record
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza

MASSIMA = (
    "Il giudice, ove ravvisi l'incompatibilita' del diritto nazionale con il diritto dell'Unione dotato di "
    "efficacia diretta, deve individuare il rimedio piu' appropriato. "
) * 12  # massima lunga: il dispositivo deve restare visibile entro il blocco


def _pronuncia(numero: str, tipologia: str, dispositivo: str) -> dict:
    return {
        "numero_pronuncia": numero,
        "anno_pronuncia": "2025",
        "data_decisione": "13/01/2025",
        "data_deposito": "27/01/2025",
        "epigrafe": "ha pronunciato la seguente&#13;nel giudizio sulla doppia pregiudizialita' europea",
        "testo": "Considerato in diritto. " * 200,
        "dispositivo": f"per questi motivi LA CORTE COSTITUZIONALE {dispositivo} Così deciso in Roma.",
        "ecli": f"ECLI:IT:COST:2025:{numero}",
        "relatore_pronuncia": "Giovanni Pitruzzella",
        "presidente": "AMOROSO",
        "tipologia_pronuncia": tipologia,
    }


class _GestoreCorpus:
    def __init__(self, corpus: GestioneCorpusGiurisprudenza):
        self.corpus = corpus

    def resolve_lex_giurisprudenza_route(self, question):
        return {"corpus_rows": self.corpus.cerca_sentenze(q=question, limit=6)}

    def cerca_corpus_professionale(self, **kwargs):
        return self.corpus.cerca_sentenze(**kwargs)


@pytest.fixture()
def fonti_consulta(tmp_path, monkeypatch):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))
    massime = {
        "tipologia_giudizio": "GIUDIZIO DI LEGITTIMITÀ COSTITUZIONALE IN VIA INCIDENTALE",
        "massime": [{"numero": "46620", "titolo": "Doppia pregiudizialita'", "testo": MASSIMA}],
    }
    corpus.salva_sentenze_blocco(
        [
            componi_record(_pronuncia("6", "S", "dichiara non fondata la questione sulla doppia pregiudizialita'."), massime),
            componi_record(_pronuncia("7", "O", "dichiara manifestamente inammissibile la doppia pregiudizialita'."), None),
        ]
    )
    monkeypatch.setattr(retrieval_giurisprudenza, "_gestore_giurisprudenza", lambda: _GestoreCorpus(corpus))

    def _cerca(query: str) -> list[EvidenceItem]:
        return GiurisprudenzaSource().search([query], SimpleNamespace(query=query), {})

    return _cerca


def test_evidence_item_porta_estremi_ecli_e_verifica(fonti_consulta):
    items = fonti_consulta("doppia pregiudizialita diritto dell'Unione")
    sentenza = next(item for item in items if item.metadata["numero_sentenza"] == "6")
    meta = sentenza.metadata
    assert sentenza.title == "Corte costituzionale, sentenza n. 6/2025"
    assert meta["organo"] == "Corte costituzionale"
    assert meta["anno_sentenza"] == "2025"
    assert meta["ecli"] == "ECLI:IT:COST:2025:6"
    assert meta["data_deposito"] == "2025-01-27"
    assert meta["stato_verifica"] == "verificata"
    assert meta["relatore"] == "Giovanni Pitruzzella"
    assert meta["tipo_provvedimento"] == "sentenza"
    assert meta["dispositivo"] == "dichiara non fondata la questione sulla doppia pregiudizialita'."
    assert meta["massima_ufficiale"].startswith("Il giudice, ove ravvisi")
    assert sentenza.official_url == "https://www.cortecostituzionale.it/scheda-pronuncia/2025/6"
    assert sentenza.verified_reference is True
    assert sentenza.trust_class == "B" and sentenza.source_level == 2


def test_intestazione_consulta_senza_numero_ripetuto(fonti_consulta):
    items = fonti_consulta("doppia pregiudizialita")
    sentenza = next(item for item in items if item.metadata["numero_sentenza"] == "6")
    ordinanza = next(item for item in items if item.metadata["numero_sentenza"] == "7")
    assert evidence_header(1, sentenza) == (
        "[1] Corte costituzionale, sentenza n. 6/2025 · ECLI:IT:COST:2025:6 · 27/01/2025"
    )
    assert evidence_header(2, ordinanza) == (
        "[2] Corte costituzionale, ordinanza n. 7/2025 · ECLI:IT:COST:2025:7 · 27/01/2025"
    )


def test_testo_fonte_massima_poi_dispositivo_entro_il_blocco(fonti_consulta):
    items = fonti_consulta("doppia pregiudizialita")
    sentenza = next(item for item in items if item.metadata["numero_sentenza"] == "6")
    blocco, _troncato = format_evidence_item(1, sentenza, max_chars=1600)
    testo = blocco.split("\n", 1)[1]
    assert len(testo) <= 1600
    assert testo.startswith("Massima: Il giudice, ove ravvisi")
    assert "Dispositivo: dichiara non fondata la questione" in testo
    assert testo.index("Massima:") < testo.index("Dispositivo:")
    # niente ripetizioni: la massima accorciata non torna in coda come «Principio»
    assert "Principio:" not in testo
    assert testo.endswith("Dispositivo: dichiara non fondata la questione sulla doppia pregiudizialita'.")
    assert "Considerato in diritto" not in testo

    ordinanza = next(item for item in items if item.metadata["numero_sentenza"] == "7")
    blocco_ord, _ = format_evidence_item(2, ordinanza)
    assert blocco_ord.split("\n", 1)[1] == "Dispositivo: dichiara manifestamente inammissibile la doppia pregiudizialita'."


def test_intestazione_cassazione_invariata_e_sezione_senza_doppione():
    item = EvidenceItem(
        source_type="giurisprudenza",
        source_id="cass",
        title="Cass. civ., sez. III, n. 12345/2024",
        content="Principio.",
        score=0.9,
        metadata={
            "organo": "Corte di cassazione",
            "numero_sentenza": "12345",
            "anno_sentenza": "2024",
            "sezione": "III",
            "data_decisione": "2024-04-02",
            "data_deposito": "2024-05-10",
        },
    )
    # numero gia' nel titolo: resta solo la sezione; la data e' quella di deposito
    assert evidence_header(3, item) == "[3] Cass. civ., sez. III, n. 12345/2024 (Corte di cassazione) · sez. III · 10/05/2024"
    # numero diverso nel titolo (es. 1234/2024 dentro 12345/2024): il riferimento resta
    altro = EvidenceItem(
        source_type="giurisprudenza", source_id="x", title="Rinvio a n. 12345/20245", content="t", score=0.1,
        metadata={"numero_sentenza": "12345", "anno_sentenza": "2024"},
    )
    assert "· n. 12345/2024" in evidence_header(1, altro)


def test_riga_non_verificata_non_e_riferimento_verificato(monkeypatch):
    righe = [
        {
            "id": 9,
            "titolo": "Tribunale di Bari, sentenza n. 10/2023",
            "organo_giudicante": "Tribunale di Bari",
            "numero_sentenza": "10",
            "anno_sentenza": 2023,
            "stato_verifica": "da_verificare",
            "url_pagina_ufficiale": "https://example.org/sentenza",
            "principio_sintetico": "Il danno va provato.",
        }
    ]

    class _Gestore:
        def resolve_lex_giurisprudenza_route(self, question):
            return {"corpus_rows": righe}

    monkeypatch.setattr(retrieval_giurisprudenza, "_gestore_giurisprudenza", lambda: _Gestore())
    (fonte,) = retrieval_giurisprudenza.search_giurisprudenza_sources("danno")
    assert fonte.metadata["verified_reference"] is False
    assert fonte.metadata["organo"] == "Tribunale di Bari"
    assert fonte.excerpt == "Principio: Il danno va provato."
