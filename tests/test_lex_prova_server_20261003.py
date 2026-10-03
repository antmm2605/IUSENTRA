"""Prova di Lex sul server del 03/10/2026 (archivio Normattiva VIGENTE completo, Qwen 3.5 9B).

Sei domande nel browser, quattro esiti da correggere:
1. domanda non giuridica (organizzare la giornata) -> fonti web a caso (Gazzetta, GDPR, una sentenza);
2. «responsabilita' extracontrattuale» -> art. 2043 c.c. trovato ma scartato dal filtro di pertinenza;
3. «entro quale termine va presentata la querela?» -> scadenziario dello studio invece dell'art. 124 c.p.;
4. «entro quanto si propone opposizione a decreto ingiuntivo?» -> trattata come richiesta di template.
"""

from __future__ import annotations

import os
from pathlib import Path

from lex.contracts import LexRequest
from lex.http_bounded_bridge import _resolve_intent, _resolve_workflow_hint
from lex.research.request_profile import classify_request
from lex.retrieval.source_router import SourceRouter
from lex.retrieval.sources.official_web import OfficialWebSource
from lex.ricerca_giuridica.classificatore import INDETERMINATA, classifica_domanda
from lex.ricerca_giuridica.ibrida import BONUS_CODICE_FONDAMENTALE, fondi_rrf
from lex.ricerca_giuridica.pertinenza import copertura_termini, e_pertinente
from lex.ricerca_giuridica.testo import analizza_domanda
from web.services.assistente_conversation_focus import resolve_conversation_focus

GIORNATA = "Scrivi tre frasi sull'organizzazione della giornata lavorativa con le pause"
RESPONSABILITA = "Quali sono gli elementi della responsabilità extracontrattuale?"
QUERELA = "Entro quale termine va presentata la querela?"
OPPOSIZIONE = "Entro quanto si propone opposizione a decreto ingiuntivo?"

ART_2043 = (
    "Art. 2043. Risarcimento per fatto illecito. Qualunque fatto doloso o colposo, che cagiona ad altri "
    "un danno ingiusto, obbliga colui che ha commesso il fatto a risarcire il danno."
)
ART_124_CP = (
    "Art. 124. Termine per proporre la querela. Rinuncia. Salvo che la legge disponga altrimenti, il diritto "
    "di querela non puo' essere esercitato, decorsi tre mesi dal giorno della notizia del fatto che costituisce il reato."
)
ART_641_CPC = (
    "Art. 641. Accoglimento della domanda. Il giudice, se ritiene fondata la domanda, pronuncia ingiunzione di "
    "pagamento, fissando il termine di quaranta giorni dalla notificazione per fare opposizione."
)
NUCLEARE = (
    "Art. 15. L'esercente e' responsabile dei danni alle persone e alle cose causati da un incidente nucleare "
    "avvenuto nell'impianto nucleare."
)


def _richiesta(domanda: str) -> LexRequest:
    return LexRequest(tenant_id="t", user_id="u", session_id="s", query=domanda)


def _profilo(domanda: str) -> tuple[dict, dict]:
    focus = resolve_conversation_focus(domanda, messages=[])
    profilo = classify_request(focus["effective_question"], requested_mode="chat")
    contesto = {"focus_topic": focus["topic"], "effective_question": focus["effective_question"]}
    return contesto, {"intent": profilo.intent, "source_mode": profilo.source_mode}


# --- 1. domanda non giuridica -------------------------------------------------------------------

def test_domanda_non_giuridica_non_cerca_fonti():
    assert classifica_domanda(GIORNATA).tipo == INDETERMINATA
    richiesta = _richiesta(GIORNATA)
    fonti = [s.__class__.__name__ for s in SourceRouter().resolve(richiesta, {}, "question_answering")]
    assert "StudioDatabaseSource" not in fonti
    assert "OfficialWebSource" not in fonti
    assert not OfficialWebSource.should_include(richiesta, "question_answering")


def test_domanda_giuridica_mantiene_la_ricerca_web_ufficiale_quando_serve():
    richiesta = _richiesta("Cosa prevede la normativa vigente sulla responsabilita' extracontrattuale? cerca sul web")
    assert OfficialWebSource.should_include(richiesta, "normativa")


def test_domanda_sullo_studio_usa_ancora_la_ricerca_studio():
    fonti = [s.__class__.__name__ for s in SourceRouter().resolve(_richiesta("Dammi le pec ricevute oggi"), {}, "question_answering")]
    assert "StudioDatabaseSource" in fonti


# --- 2. art. 2043 c.c. ---------------------------------------------------------------------------

def test_2043_e_pertinente_per_la_responsabilita_extracontrattuale():
    assert copertura_termini(RESPONSABILITA, ART_2043) == 1.0
    assert e_pertinente(RESPONSABILITA, ART_2043)


def test_una_sola_parola_comune_non_basta_per_il_tesauro():
    # «danno» compare nella legge sui danni nucleari, ma non le parole dell'art. 2043
    assert copertura_termini(RESPONSABILITA, "Il danno e' liquidato dal giudice.") < 0.34


def test_codici_fondamentali_prima_delle_leggi_speciali_a_parita_di_rango():
    analisi = analizza_domanda(RESPONSABILITA)
    lessicali = []
    semantici = [(2, 0.80), (1, 0.79)]  # la legge speciale e' prima per il coseno
    info = {
        1: ("2043", "codice_civile", "262", "1942", "VIGENTE", "cc-2043", 1),
        2: ("15", "", "1860", "1962", "VIGENTE", "l1860-15", 1),
    }
    fusi = fondi_rrf(lessicali, semantici, info, analisi=analisi, esatti=set())
    assert [r.chunk_id for r in fusi] == [1, 2]
    assert fusi[0].punteggio - fusi[1].punteggio <= BONUS_CODICE_FONDAMENTALE


def test_nessun_bonus_se_la_domanda_indica_un_atto():
    analisi = analizza_domanda("Cosa prevede l'art. 15 della legge 1860/1962?")
    info = {
        1: ("2043", "codice_civile", "262", "1942", "VIGENTE", "cc-2043", 1),
        2: ("15", "", "1860", "1962", "VIGENTE", "l1860-15", 1),
    }
    fusi = fondi_rrf([], [(2, 0.8), (1, 0.79)], info, analisi=analisi, esatti=set())
    assert fusi[0].chunk_id == 2


def test_banco_responsabilita_extracontrattuale_trova_2043_pertinente(tmp_path):
    os.environ.setdefault("LEX_RICERCA_SEMANTICA", "0")
    from tests.lex_fonti_banco.valutazione import costruisci_db
    from lex.ricerca_giuridica.ibrida import cerca_normattiva_indicizzata

    db = costruisci_db(Path(tmp_path) / "banco.sqlite")
    righe = cerca_normattiva_indicizzata(RESPONSABILITA, db, limite=8) or []
    pertinenti = [
        str((r.get("metadata") or {}).get("article_number"))
        for r in righe
        if e_pertinente(RESPONSABILITA, " ".join(str(r.get(k) or "") for k in ("titolo", "testo", "excerpt")))
    ]
    assert pertinenti[:1] == ["2043"]


# --- 3. querela ------------------------------------------------------------------------------------

def test_querela_e_una_domanda_di_diritto_non_di_scadenziario():
    c = classifica_domanda(QUERELA)
    assert c.giuridica and c.tipo_ricerca == "normativa"
    focus = resolve_conversation_focus(QUERELA, messages=[])
    assert focus["topic"] == ""
    contesto, profilo = _profilo(QUERELA)
    assert profilo["intent"] == "normativa"
    assert _resolve_intent(QUERELA, contesto, profilo) == "research_normativa"


def test_scadenze_dello_studio_restano_allo_scadenziario():
    focus = resolve_conversation_focus("Quali sono le mie scadenze di domani?", messages=[])
    assert focus["topic"] == "scadenze"


def test_124_cp_e_pertinente_per_il_termine_della_querela():
    assert e_pertinente(QUERELA, ART_124_CP)


# --- 4. opposizione a decreto ingiuntivo -----------------------------------------------------------

def test_domanda_sull_opposizione_non_e_una_richiesta_di_template():
    contesto, profilo = _profilo(OPPOSIZIONE)
    assert _resolve_workflow_hint(contesto, profilo) == "normativa"
    assert _resolve_intent(OPPOSIZIONE, contesto, profilo) == "research_normativa"
    assert e_pertinente(OPPOSIZIONE, ART_641_CPC)


def test_richiesta_di_redazione_resta_al_template():
    domanda = "Prepara un atto di opposizione a decreto ingiuntivo"
    contesto, profilo = _profilo(domanda)
    assert _resolve_workflow_hint(contesto, profilo) == "atto_da_template"


def test_legge_nucleare_non_pertinente_per_la_querela():
    assert not e_pertinente(QUERELA, NUCLEARE)
