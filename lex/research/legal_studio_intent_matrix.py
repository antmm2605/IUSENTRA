"""Matrice intenti professionali per Lex — studio legale italiano.

13 macro-intenti coprono l'intera operatività di un avvocato:
dal fascicolo alla firma, dal preventivo alla giurisprudenza.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MacroIntent:
    key: str
    label: str
    description: str
    workflows: tuple[str, ...]
    example_queries: tuple[str, ...]
    patterns: tuple[str, ...]
    priority: int
    requires_context: tuple[str, ...]
    response_schema: tuple[str, ...]
    provider_hint: str
    disclaimer_suppressed: bool = True
    english_forbidden: bool = True


_INTENT_MATRIX: tuple[MacroIntent, ...] = (

    MacroIntent(
        key="lex_feedback_diagnostico",
        label="Feedback e diagnosi Lex",
        description=(
            "L'utente corregge o contesta una risposta precedente di Lex. "
            "Lex deve riconoscerlo, riformulare se opportuno, non essere difensivo."
        ),
        workflows=("lex_feedback_diagnostico",),
        example_queries=(
            "non hai capito",
            "risposta sbagliata",
            "non è quello che intendevo",
            "Lex ha sbagliato",
            "no, intendevo altro",
            "riprova",
            "sei fuori strada",
            "non è corretto",
            "non era questa la domanda",
            "la tua risposta è errata",
        ),
        patterns=(
            r"\bnon hai capito\b",
            r"\bnon (\w+ )?(?:corretto|giust[ao]|quello|esatto)\b",
            r"\brisposta sbagliata\b",
            r"\bsei fuori strada\b",
            r"\bintendevo\b.*\baltro\b",
            r"\briprova\b",
            r"\bnon era questa\b",
            r"\blex ha sbagliato\b",
            r"\bhai frainteso\b",
            r"\bcorreggiti\b",
        ),
        priority=1,
        requires_context=(),
        response_schema=("Comprensione", "Riformulazione", "Proposta corretta"),
        provider_hint="deterministic",
    ),

    MacroIntent(
        key="redazione_legale",
        label="Redazione lettere, diffide e atti",
        description=(
            "Redazione di lettere legali, diffide, messe in mora, PEC formali, "
            "atti processuali, memorie, ricorsi, comparse. Output sempre in italiano."
        ),
        workflows=("drafting_legal_letter", "atto", "bozza_lettera", "bozza_atto"),
        example_queries=(
            "scrivi una diffida al condominio",
            "prepara una messa in mora",
            "redigi una PEC formale al debitore",
            "bozza di citazione in giudizio",
            "memoria difensiva per l'udienza",
            "lettera di sollecito pagamento",
            "atto di contestazione",
            "ricorso al TAR",
            "comparsa di risposta",
            "invito formale a stipula del contratto",
        ),
        patterns=(
            r"\bdiffida\b",
            r"\bmessa in mora\b",
            r"\bcostituzione in mora\b",
            r"\bintimazione\b",
            r"\blettera legale\b",
            r"\bpec (?:formale|legale)\b",
            r"\bsollecito\b",
            r"\bscrivi(?:mi)?\s+una?\b",
            r"\bredigi(?:mi)?\b",
            r"\bprepara(?:mi)?\s+una?\b",
            r"\bbozza\b",
            r"\bmemoria\b",
            r"\bricorso\b",
            r"\bcomparsa\b",
            r"\bcitazione (?:in giudizio)?\b",
        ),
        priority=2,
        requires_context=(),
        response_schema=("Bozza", "Punti da adattare", "Avvertenze", "Fonti e affidabilita"),
        provider_hint="ollama",
    ),

    MacroIntent(
        key="agenda_scadenze_termini",
        label="Agenda, scadenze e calcolo termini",
        description=(
            "Calcolo deterministico di termini processuali, scadenze di studio, "
            "udienze in calendario, promemoria e alert. Logica basata su norme processuali italiane."
        ),
        workflows=("termini_processuali", "cabina", "next_action"),
        example_queries=(
            "calcola il termine per l'opposizione al decreto ingiuntivo",
            "quando scade il termine per appellare",
            "scadenze di questa settimana",
            "termini processuali per il rito sommario",
            "calcola i giorni per la notifica",
            "udienze di domani",
            "cosa scade oggi",
            "termine per la costituzione in giudizio",
            "scadenza per il ricorso al TAR",
            "30 giorni dalla notifica: quando scade",
        ),
        patterns=(
            r"\btermini? (?:process|notif|ricors|appell)\w*\b",
            r"\bscadenz",
            r"\bcalcola (?:il )?termine\b",
            r"\bquando scade\b",
            r"\btermine per\b",
            r"\budienz",
            r"\bopposizione entro\b",
            r"\bappello entro\b",
            r"\bnotifica entro\b",
            r"\bgiorni dalla notifica\b",
        ),
        priority=3,
        requires_context=(),
        response_schema=("Scadenza calcolata", "Normativa applicata", "Avvertenze", "Prossima azione"),
        provider_hint="deterministic",
    ),

    MacroIntent(
        key="telematico_deposito",
        label="Deposito telematico e portali",
        description=(
            "Checklist, guida e diagnosi per depositi telematici su PST/polisWeb, "
            "PDP (penale), PAT (amministrativo), PTT, SIGP. Errori, stati e rimedi."
        ),
        workflows=("deposito_telematico", "telematico_status", "compliance"),
        example_queries=(
            "come deposito il ricorso al TAR",
            "errore PST nella busta enc",
            "il deposito penale PDP non va",
            "checklist per il deposito civile",
            "stato del deposito telematico",
            "formato PDF/A per il deposito",
            "firma CAdES per PST",
            "PAT: documenti obbligatori per TAR",
            "cosa serve per il deposito su polisweb",
            "errore nel DatiAtto.xml",
        ),
        patterns=(
            r"\bpst\b",
            r"\bpdp\b",
            r"\bpat\b",
            r"\bptt\b",
            r"\bsigp\b",
            r"\bpolisweb\b",
            r"\bdeposito telematico\b",
            r"\berrore (?:pst|pdp|pat|busta|telematico)\b",
            r"\bchecklist deposito\b",
            r"\bbusta (?:enc|telematica)\b",
            r"\bfirma cades\b",
            r"\bpdf/a\b",
            r"\bdatiatto\b",
        ),
        priority=4,
        requires_context=(),
        response_schema=("Checklist", "Portale", "Requisiti tecnici", "Diagnosi errori", "Prossima azione"),
        provider_hint="deterministic",
    ),

    MacroIntent(
        key="pec_comunicazioni",
        label="PEC e comunicazioni ufficiali",
        description=(
            "Redazione PEC formali, verifica PEC ricevute, gestione ricevute di accettazione "
            "e consegna, comunicazioni con cancellerie e controparti."
        ),
        workflows=("drafting_legal_letter", "question_answering"),
        example_queries=(
            "bozza PEC per la controparte",
            "invia PEC alla cancelleria",
            "verifica ricevuta PEC",
            "la PEC non è arrivata",
            "PEC di messa in mora",
            "PEC di risposta al sollecito",
            "come si struttura una PEC legale",
            "ricevuta di accettazione PEC",
            "PEC di diffida al condominio",
        ),
        patterns=(
            r"\bpec\b.*(?:forma|legal|cancelleria|diffida|manda|invia|bozza|scrivi)\b",
            r"\b(?:manda|invia|prepara)\b.*\bpec\b",
            r"\bricevuta pec\b",
            r"\bposta elettronica certificata\b",
        ),
        priority=5,
        requires_context=(),
        response_schema=("Bozza PEC", "Oggetto", "Destinatario", "Avvertenze"),
        provider_hint="ollama",
    ),

    MacroIntent(
        key="fascicolo_operativo",
        label="Gestione fascicolo e pratiche",
        description=(
            "Accesso, sintesi e aggiornamento di fascicoli attivi, "
            "ricerca pratiche per cliente o numero, quadro della pratica."
        ),
        workflows=("fascicolo", "next_action"),
        example_queries=(
            "stato del fascicolo Rossi",
            "apri la pratica 2024/1234",
            "sintesi del fascicolo",
            "documenti del fascicolo",
            "prossima udienza del fascicolo",
            "attività processuali della pratica",
            "cliente Bianchi: pratiche attive",
            "ultime comunicazioni del fascicolo",
        ),
        patterns=(
            r"\bfascicolo\b",
            r"\bpratica\b",
            r"\bstato (?:del |della )?(?:fascicolo|pratica)\b",
            r"\bsintesi (?:del |della )?(?:fascicolo|pratica)\b",
            r"\bdocumenti (?:del |della )?(?:fascicolo|pratica)\b",
        ),
        priority=6,
        requires_context=("fascicolo_id",),
        response_schema=("Quadro pratica", "Documenti chiave", "Scadenze", "Prossime azioni"),
        provider_hint="deterministic",
    ),

    MacroIntent(
        key="analisi_documentale",
        label="Analisi e revisione documenti",
        description=(
            "Analisi di contratti, atti, PDF, estratti, relazioni peritali. "
            "Estrazione punti chiave, rischi, lacune, obblighi."
        ),
        workflows=("documento", "fascicolo", "research"),
        example_queries=(
            "analizza questo contratto",
            "riassumi il PDF",
            "trova le clausole critiche",
            "rischi del contratto di locazione",
            "estrai le obbligazioni principali",
            "clausola penale nel contratto",
            "lacune nell'accordo di separazione",
            "analisi della perizia tecnica",
        ),
        patterns=(
            r"\banalizza\b",
            r"\banalisi (?:del |del contratto|della|del |di)\b",
            r"\bcontratto\b.*(?:rischi|clausol|obbligo|lacun)\b",
            r"\briassumi (?:il |la |questo |questa )?\b(?:pdf|documento|contratto|perizia|accordo|atto)\b",
            r"\bestrai\b.*(?:clausol|obblig|punti)\b",
        ),
        priority=7,
        requires_context=("document_id",),
        response_schema=("Sintesi", "Punti chiave", "Rischi o lacune", "Obblighi", "Prossime azioni"),
        provider_hint="ollama",
    ),

    MacroIntent(
        key="giurisprudenza",
        label="Ricerca giurisprudenziale",
        description=(
            "Ricerca sentenze, massime, pronunce di Cassazione, TAR, Consiglio di Stato, "
            "Corti d'appello. Orientamenti consolidati e contrasti."
        ),
        workflows=("giurisprudenza", "giurisprudenza_specifica", "research"),
        example_queries=(
            "sentenze sulla responsabilità medica",
            "giurisprudenza sull'usucapione",
            "massima Cassazione su risarcimento danni",
            "orientamento TAR su appalti pubblici",
            "pronunce recenti sull'art. 1218 c.c.",
            "sentenza Cass. Civ. n. 12345/2023",
            "contrasto giurisprudenziale sulla fideiussione",
        ),
        patterns=(
            r"\bsentenz",
            r"\bgiurisprudenz",
            r"\bmassima\b",
            r"\bpronunci",
            r"\bcassazione\b",
            r"\btar\b.*(?:sentenz|ricors|orient)\b",
            r"\bconsiglio di stato\b",
            r"\borientamento (?:giurisprudenziale|dei giudici)\b",
        ),
        priority=8,
        requires_context=(),
        response_schema=("Riferimento", "Massima o estratto", "Orientamento consolidato", "Applicazione pratica", "Fonti"),
        provider_hint="ollama",
    ),

    MacroIntent(
        key="normativa",
        label="Ricerca normativa e aggiornamenti",
        description=(
            "Verifica testi di legge, decreti, regolamenti, norme vigenti. "
            "Aggiornamenti normativi, novità legislative, GU."
        ),
        workflows=("normativa", "intelligence", "fonti"),
        example_queries=(
            "art. 1218 codice civile testo vigente",
            "decreto 44/2011 deposito telematico",
            "ultime modifiche al codice di procedura civile",
            "D.Lgs. 150/2022 riforma penale",
            "normativa sull'usura: tassi vigenti",
            "cosa dice l'art. 96 c.p.c.",
            "novità legislative in materia di lavoro",
        ),
        patterns=(
            r"\bnorm",
            r"\blegge\b",
            r"\bdecreto\b",
            r"\bart(?:icolo)?\.?\s*\d+\b",
            r"\bc\.c\.\b",
            r"\bc\.p\.c\.\b",
            r"\bcodice\b.*(?:civile|penale|procedura)\b",
            r"\bgazzetta ufficiale\b",
            r"\bvigente\b",
            r"\bd\.lgs\.\b",
            r"\bd\.m\.\b",
        ),
        priority=9,
        requires_context=(),
        response_schema=("Testo normativo", "Applicazione pratica", "Aggiornamenti", "Limiti", "Fonti"),
        provider_hint="ollama",
    ),

    MacroIntent(
        key="economico_forense",
        label="Calcoli economici e tariffario forense",
        description=(
            "Calcolo compensi DM 55/2014, DM 147/2022, DM 150/2023. "
            "Preventivi, parcelle, tabelle scaglioni, rimborso spese."
        ),
        workflows=("economico", "cabina"),
        example_queries=(
            "calcola il compenso DM 55 per causa di valore 50.000 euro",
            "tariffario forense fase istruttoria",
            "parcella per causa di lavoro",
            "scaglioni DM 147",
            "compenso minimo per fase decisionale",
            "rimborso spese forfettario 15%",
            "preventivo per separazione consensuale",
            "tabella A DM 55 scaglione 3",
        ),
        patterns=(
            r"\bd\.?m\.?\s*5[57]\b",
            r"\bd\.?m\.?\s*14[57]\b",
            r"\bd\.?m\.?\s*150\b",
            r"\bcompenso\b",
            r"\bonorario\b",
            r"\btariffario\b",
            r"\bscaglione\b",
            r"\bparcella\b",
            r"\bpreventivo\b.*(?:causa|giudizio|legale|forense)\b",
            r"\brimborso spese\b",
            r"\btabella a\b.*\bforense\b",
        ),
        priority=10,
        requires_context=(),
        response_schema=("Calcolo compenso", "Scaglione applicato", "Fasi liquidate", "Normativa", "Totale stimato"),
        provider_hint="deterministic",
    ),

    MacroIntent(
        key="fatturazione_incassi",
        label="Fatturazione, parcelle e pagamenti",
        description=(
            "Gestione fatture emesse, parcelle da incassare, "
            "stato pagamenti, solleciti, riconciliazione."
        ),
        workflows=("economico", "cabina"),
        example_queries=(
            "fatture non pagate",
            "stato pagamento parcella Rossi",
            "emetti fattura per la pratica 2024/100",
            "incassi del mese",
            "parcelle scadute",
            "genera nota spese",
        ),
        patterns=(
            r"\bfattur",
            r"\bparcell",
            r"\bpagament",
            r"\bincasso\b",
            r"\bnota spese\b",
            r"\bsollecito pagamento\b",
            r"\bfatture non pagate\b",
        ),
        priority=11,
        requires_context=(),
        response_schema=("Stato economico", "Importi", "Azioni", "Prossima azione"),
        provider_hint="deterministic",
    ),

    MacroIntent(
        key="cabina_studio",
        label="Cabina di regia studio",
        description=(
            "Overview operativa della giornata: scadenze urgenti, udienze, agenda, "
            "fascicoli attivi, comunicazioni e attività prioritarie."
        ),
        workflows=("cabina", "next_action"),
        example_queries=(
            "cosa c'è da fare oggi",
            "quadro operativo dello studio",
            "scadenze urgenti",
            "situazione studio",
            "dashboard operativa",
            "priorità di oggi",
            "udienze di questa settimana",
            "cosa devo fare prima",
        ),
        patterns=(
            r"\bcosa (?:c'è da fare|devo fare|ho da fare)\b",
            r"\bquadro operativo\b",
            r"\bsituazione studio\b",
            r"\bdashboard\b",
            r"\bpriori(?:tà|ta)\b.*(?:oggi|studio|giorno)\b",
            r"\bda dove (?:parto|inizio|partiamo)\b",
        ),
        priority=12,
        requires_context=(),
        response_schema=("Panoramica", "Urgenze", "Agenda", "Prossime azioni"),
        provider_hint="deterministic",
    ),

    MacroIntent(
        key="strategia_legale",
        label="Strategia e ragionamento legale",
        description=(
            "Valutazione rischi, pareri, analisi tesi difensive, "
            "strategie processuali, orientamenti e consigli professionali."
        ),
        workflows=("normativa", "giurisprudenza", "research", "fascicolo"),
        example_queries=(
            "quali sono le opzioni difensive",
            "rischi dell'azione in giudizio",
            "conviene transare",
            "analisi della posizione giuridica",
            "tesi difensiva più forte",
            "parere sull'ammissibilità",
            "vale la pena fare ricorso",
            "strategia per il processo civile",
        ),
        patterns=(
            r"\bstrategi",
            r"\bopzioni (?:difensive|legali|processuali)\b",
            r"\brischi (?:del|dell|della|di)\b.*(?:causa|ricorso|azione|giudizio)\b",
            r"\bparere\b",
            r"\bconviene\b.*(?:trans|ricors|appeal|giudizio)\b",
            r"\btesi difensiva\b",
            r"\bammissibilita\b",
        ),
        priority=13,
        requires_context=(),
        response_schema=("Valutazione", "Opzioni", "Rischi", "Raccomandazione", "Fonti e affidabilita"),
        provider_hint="ollama",
    ),
)

_MATRIX_BY_KEY: dict[str, MacroIntent] = {m.key: m for m in _INTENT_MATRIX}
_PRIORITY_ORDER: tuple[MacroIntent, ...] = tuple(
    sorted(_INTENT_MATRIX, key=lambda m: m.priority)
)


def get_intent(key: str) -> MacroIntent | None:
    return _MATRIX_BY_KEY.get(key)


def all_intents() -> tuple[MacroIntent, ...]:
    return _PRIORITY_ORDER


def intent_keys() -> tuple[str, ...]:
    return tuple(m.key for m in _PRIORITY_ORDER)


def workflow_for_intent(key: str) -> str:
    intent = _MATRIX_BY_KEY.get(key)
    if intent and intent.workflows:
        return intent.workflows[0]
    return "question_answering"


def response_schema_for_intent(key: str) -> tuple[str, ...]:
    intent = _MATRIX_BY_KEY.get(key)
    if intent:
        return intent.response_schema
    return ("Risposta", "Fonti e affidabilita")


def classify_from_matrix(question: str) -> MacroIntent | None:
    """Classifica una domanda usando la matrice a priorità."""
    import re

    clean = " ".join(str(question or "").split()).lower()
    if not clean:
        return None
    for intent in _PRIORITY_ORDER:
        for pattern in intent.patterns:
            try:
                if re.search(pattern, clean):
                    return intent
            except re.error:
                continue
    return None


__all__ = [
    "MacroIntent",
    "all_intents",
    "classify_from_matrix",
    "get_intent",
    "intent_keys",
    "response_schema_for_intent",
    "workflow_for_intent",
]
