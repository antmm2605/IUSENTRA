"""Revisione 2.410.0: Lex risponde con calcoli certi, si astiene senza fonti pertinenti."""

from __future__ import annotations

from types import SimpleNamespace

from lex.formatting.professional_answer import ProfessionalAnswerComposer
from lex.guards.evidence_relevance_guard import PertinenzaFontiGuard, evidenza_pertinente
from lex.guards.hallucination_guard import extract_legal_references
from lex.risposte_certe import date_nella_domanda, importo_nella_domanda, risposta_certa
from lex.router import _contiene


def test_memorie_171_ter_calcolate_a_ritroso():
    esito = risposta_certa("Quali sono i termini delle memorie 171-ter se l'udienza è il 20 gennaio 2027?")
    assert esito is not None
    assert "10/12/2026" in esito.testo and "30/12/2026" in esito.testo and "08/01/2027" in esito.testo
    assert "11/11/2026" in esito.testo  # costituzione del convenuto, 70 giorni


def test_appello_breve_lungo_e_cassazione():
    breve = risposta_certa("Entro quanto devo proporre appello contro una sentenza civile notificata il 3 marzo 2026?")
    assert "02/04/2026" in breve.testo and "art. 325" in breve.testo
    lungo = risposta_certa("Sentenza pubblicata il 15/05/2026 non notificata: termine per appello?")
    assert "16/12/2026" in lungo.testo and "art. 327" in lungo.testo  # sei mesi + sospensione feriale
    cassazione = risposta_certa("Entro quando il ricorso per cassazione, sentenza notificata il 2/9/2026?")
    assert "02/11/2026" in cassazione.testo  # 1° novembre festivo e domenica
    assert risposta_certa("appello penale termine?") is None


def test_opposizione_decreto_ingiuntivo_con_sospensione_feriale():
    esito = risposta_certa("Il termine per l'opposizione a decreto ingiuntivo notificato il 10/07/2026?")
    assert "21/09/2026" in esito.testo
    senza_data = risposta_certa("Il termine per l'opposizione a decreto ingiuntivo?")
    assert "40 giorni" in senza_data.testo and "Indicami la data" in senza_data.testo


def test_contributo_unificato_decreto_ingiuntivo():
    esito = risposta_certa("Quanto è il contributo unificato per un decreto ingiuntivo di 42.350 euro?")
    assert "259,00" in esito.testo
    assert "art. 13" in esito.testo
    chiede = risposta_certa("Quanto costa il contributo unificato?")
    assert "valore della causa" in chiede.testo


def test_estrazione_date_e_importi():
    assert [d.isoformat() for d in date_nella_domanda("dal 3 marzo 2026 al 20/01/2027")] == ["2026-03-03", "2027-01-20"]
    assert importo_nella_domanda("un credito di € 42.350,50") == 42350.5
    assert importo_nella_domanda("42.350 euro") == 42350.0


def test_fonti_non_pertinenti_bloccano_la_risposta():
    assert not evidenza_pertinente("Cosa prevede l'art. 2043 c.c.?", "Impostazioni studio: denominazione")
    assert evidenza_pertinente("Cosa prevede l'art. 2043 c.c.?", "Art. 2043 c.c. — risarcimento per fatto illecito")
    verdetto = PertinenzaFontiGuard().check(
        workflow="question_answering",
        request=SimpleNamespace(query="Cosa prevede l'art. 2043 c.c.?"),
        evidence={"items": [{"title": "Impostazioni studio", "excerpt": "PEC e canali email"}]},
    )
    assert verdetto.allowed is False
    assert PertinenzaFontiGuard().check(workflow="fascicolo", request=SimpleNamespace(query="x"), evidence={"items": [{}]}).allowed


def test_astensione_senza_elenco_di_fonti():
    risultato = ProfessionalAnswerComposer().compose(
        request=SimpleNamespace(query="art. 2043"),
        context={},
        workflow="normativa",
        draft_text="Non posso completare una risposta legale affidabile con i riferimenti oggi verificati.",
        risk_level="medium",
        confidence=0.2,
        answer_mode="needs_review",
        evidence_count=5,
        official_sources=["Banca d'Italia"],
        trusted_sources=["Impostazioni studio"],
        considered_sources=[],
        missing_evidence=[],
        evidence_sufficient=False,
        fallback_triggered=False,
        existing_next_actions=[],
    )
    assert "Dato certo" not in risultato.answer and "Fonti consultate" not in risultato.answer


def test_router_parole_intere_e_riferimenti_normativi():
    assert not _contiene("devo presentare il ricorso", "tar")
    assert _contiene("ricorso al tar lazio", "tar")
    assert not _contiene("patrocinio a spese dello stato", "pat")
    riferimenti = {r.label.lower() for r in extract_legal_references("ai sensi dell'articolo 2043 c.c. e della L. 689/1981")}
    assert any("2043" in r for r in riferimenti) and any("689" in r for r in riferimenti)
