from __future__ import annotations

from scripts.curate_codex_guida_pratica_completion import curate_item, infer_profile
from scripts.import_guida_pratica_termini_processuali import classify


def test_codex_curation_distingue_atp_cautelare_e_impresa():
    atp = {
        "codice": "012002",
        "denominazione": "Consulenza tecnica preventiva (art. 696-bis cpc.)",
        "categoria": "Procedimenti speciali sommari",
        "sottocategoria": "Procedimenti cautelari ante causam - istruzione preventiva",
        "rito": "Procedimento cautelare o istruzione preventiva",
    }
    cautelare = {
        "codice": "014002",
        "denominazione": "Provvedimenti cautelari in materia di tutela della concorrenza e del mercato",
        "categoria": "Procedimenti speciali sommari",
        "sottocategoria": "Procedimenti cautelari davanti alla Corte di Appello",
        "rito": "Procedimento cautelare o istruzione preventiva",
    }
    impresa = {
        "codice": "181026",
        "denominazione": "Tutela segreti commerciali (art. 98 c.p.i.)",
        "categoria": "Contenzioso civile",
        "sottocategoria": "Sezione specializzata dell'impresa",
        "rito": "Volontaria giurisdizione",
    }

    assert infer_profile(atp) == "atp_istruzione_preventiva"
    assert infer_profile(cautelare) == "cautelare"
    assert infer_profile(impresa) == "impresa_societario"


def test_codex_curation_aggiunge_fonti_e_contesto_lex():
    item = {
        "codice": "014002",
        "denominazione": "Provvedimenti cautelari in materia di tutela della concorrenza e del mercato",
        "categoria": "Procedimenti speciali sommari",
        "sottocategoria": "Procedimenti cautelari davanti alla Corte di Appello",
        "rito": "Procedimento cautelare o istruzione preventiva",
        "atto_principale": {"campi_obbligatori": []},
        "allegati_obbligatori": [],
    }

    curated = curate_item(item)

    assert curated["_quality_hint"] == "curata_codex_fonti_ufficiali"
    assert curated["ricerca_curata_codex"]["stato"] == "curata_con_fonti_ufficiali"
    assert curated["guida_operativa_curata"]["non_bloccante"] is True
    assert "Lex deve partire dal fascicolo" in curated["guida_operativa_curata"]["lex_context"]
    assert any(source["fonte"] == "Normattiva" for source in curated["ricerca_curata_codex"]["fonti_ufficiali"])
    assert any(term.get("giorni") == 15 for term in curated["termini_processuali"])
    assert curated["tipologie_di_intervento"]
    assert curated["legittimati_attivi"]
    assert curated["obbligo_mediazione"]["stato"] in {"da_verificare", "normalmente_non_preventiva"}
    assert curated["richiesta_provvedimenti_urgenti"]["ammissibile"]
    assert curated["avvertimenti_obbligatori"]
    assert curated["esiti_processuali_tipici"]


def test_presidio_non_numerico_resta_manual_review():
    classification, calculable, note = classify(
        {
            "termine": "Termini fissati dal giudice o dalla cancelleria nel provvedimento di trattazione",
            "decorrenza": "Dalla comunicazione del provvedimento",
            "norma": "c.p.c. art. 155",
            "richiede_verifica_avvocato": True,
        }
    )

    assert classification == "manual_review"
    assert calculable is False
    assert "verifica professionale" in note
