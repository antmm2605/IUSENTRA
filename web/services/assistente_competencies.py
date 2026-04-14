"""Registro unico delle competenze operative di Lex nel software."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LexCompetenceProfile:
    topic: str
    label: str
    focus_label: str
    keywords: tuple[str, ...]
    section_titles: tuple[str, ...]
    prompt_block: str
    context_hint: str
    include_live_web: bool = False
    research_strategy: str = ""


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _contains_query_token(question: str, token: str) -> bool:
    haystack = _clean_spaces(question).lower()
    needle = _clean_spaces(token).lower()
    if not haystack or not needle:
        return False
    if len(needle) <= 4 and needle.isalpha():
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None
    return needle in haystack


_COMPETENCE_PROFILES: tuple[LexCompetenceProfile, ...] = (
    LexCompetenceProfile(
        topic="dashboard_operativo",
        label="Centro operativo dello studio",
        focus_label="quadro operativo generale",
        keywords=(
            "dashboard",
            "panoramica",
            "quadro generale",
            "situazione studio",
            "come siamo messi",
            "overview",
            "riepilogo generale",
        ),
        section_titles=("Impostazioni studio", "Quadro operativo", "Agenda", "Scadenziario"),
        prompt_block=(
            "Competenza HACS: Centro operativo dello studio. Quando l'utente chiede una panoramica o un quadro generale, "
            "Lex deve ordinare la risposta per priorita', distinguere cosa richiede attenzione oggi e indicare la prossima attivita' utile."
        ),
        context_hint=(
            "Usa il quadro operativo solo quando l'utente chiede davvero una vista generale dello studio o della giornata."
        ),
    ),
    LexCompetenceProfile(
        topic="telematico",
        label="Centro Servizi Telematici",
        focus_label="portali telematici e depositi",
        keywords=(
            "pst",
            "polisweb",
            "pdp",
            "pat",
            "siga",
            "ptt",
            "sigit",
            "deposito telematico",
            "busta",
            "datiatto",
            "formweb",
            "accesso atti",
            "tribunale telematico",
            "portale servizi telematici",
            "cabina telematica",
        ),
        section_titles=("Centro Servizi Telematici", "Fascicoli", "PEC e canali email", "Applicazioni", "Ricerca legale e fonti web"),
        prompt_block=(
            "Competenza HACS: Centro Servizi Telematici. Se il tema riguarda PST, PDP, PAT/SIGA, PTT/SIGIT, import fascicoli, "
            "depositi o autenticazioni ai portali, Lex deve distinguere il canale corretto, chiarire prerequisiti tecnici e documentali "
            "e indicare il prossimo passo pratico nel gestionale. Deve usare il repository telematico strutturato: catalogo PST, "
            "fonti ufficiali, capability reali, azioni disponibili, regole tecniche, canali XSD/WSDL e monitoraggio."
        ),
        context_hint=(
            "Per i portali telematici resta concreta: canale corretto, prerequisiti, import disponibile, limiti busta, stato XSD/WSDL, "
            "necessita' di certificato o handoff e prossimo passo."
        ),
    ),
    LexCompetenceProfile(
        topic="fascicoli",
        label="Fascicoli e procedimenti",
        focus_label="fascicoli e procedimenti rilevanti",
        keywords=(
            "fascicolo",
            "fascicoli",
            "pratica",
            "pratiche",
            "procedimento",
            "procedimenti",
            "rg",
            "causa",
            "controparte",
            "giudice",
        ),
        section_titles=("Fascicoli", "Agenda", "Scadenziario"),
        prompt_block=(
            "Competenza HACS: Fascicoli e procedimenti. Quando la richiesta tocca stato pratica, RG, controparte, giudice o fase, "
            "Lex deve collegare la risposta ai fascicoli concreti e segnalare subito prossima udienza, attivita' aperte o elementi mancanti."
        ),
        context_hint=(
            "Collega sempre la risposta ai fascicoli concreti, non a spiegazioni astratte sul procedimento."
        ),
    ),
    LexCompetenceProfile(
        topic="udienze_agenda_scadenze",
        label="Udienze, agenda e scadenze",
        focus_label="udienze, agenda e adempimenti imminenti",
        keywords=(
            "udienza",
            "udienze",
            "agenda",
            "appuntamento",
            "appuntamenti",
            "calendario",
            "scadenza",
            "scadenze",
            "termine",
            "termini",
            "promemoria",
            "oggi",
            "domani",
        ),
        section_titles=("Agenda", "Scadenziario", "Fascicoli"),
        prompt_block=(
            "Competenza HACS: Udienze, agenda e scadenze. Ordina sempre prima gli eventi piu' vicini nel tempo, chiarisci il criterio usato "
            "e proponi una selezione breve come oggi, prossime, urgenti o collegate ai fascicoli attivi."
        ),
        context_hint=(
            "Per udienze e scadenze mostra prima cio' che scade o si tiene prima, poi i dettagli utili al lavoro."
        ),
    ),
    LexCompetenceProfile(
        topic="clienti_soggetti",
        label="Clienti, soggetti e anagrafiche",
        focus_label="anagrafiche clienti e soggetti",
        keywords=(
            "cliente",
            "clienti",
            "assistito",
            "assistiti",
            "anagrafica",
            "anagrafiche",
            "soggetto",
            "soggetti",
            "parte",
            "parti",
            "difensore",
            "codifensore",
            "domiciliatario",
            "pec cliente",
        ),
        section_titles=("Clienti", "Soggetti", "Fascicoli"),
        prompt_block=(
            "Competenza HACS: Clienti, soggetti e anagrafiche. Richiama solo i dati utili, chiarisci ruolo processuale e riferimenti essenziali "
            "e segnala subito se mancano recapiti, collegamenti a fascicolo o dati identificativi importanti."
        ),
        context_hint=(
            "Usa l'anagrafica in modo mirato: chi e' coinvolto, con quale ruolo e quali dati mancano davvero."
        ),
    ),
    LexCompetenceProfile(
        topic="documenti_rag",
        label="Documenti e retrieval locale",
        focus_label="documenti, allegati e retrieval locale",
        keywords=(
            "documento",
            "documenti",
            "allegato",
            "allegati",
            "verbale",
            "pdf",
            "documentazione",
            "ricerca nel documento",
            "rag",
            "retrieval",
            "indice allegati",
        ),
        section_titles=("RAG documentale locale", "Fascicoli", "Template atti"),
        prompt_block=(
            "Competenza HACS: Documenti e retrieval locale. Se l'utente cerca un documento o un contenuto nei documenti, "
            "Lex deve partire dagli allegati e dal retrieval locale disponibili, citare il documento pertinente e dire cosa emerge davvero."
        ),
        context_hint=(
            "Quando il tema e' documentale, usa prima il retrieval locale e i fascicoli collegati."
        ),
    ),
    LexCompetenceProfile(
        topic="atti_template",
        label="Atti, template e catalogo atti",
        focus_label="atti, modelli e redazione",
        keywords=(
            "atto",
            "atti",
            "template",
            "modello",
            "modelli",
            "bozza",
            "redazione",
            "catalogo atti",
            "ricorso",
            "comparsa",
            "citazione",
            "memoria",
            "precetto",
        ),
        section_titles=("Template atti", "Fascicoli", "RAG documentale locale"),
        prompt_block=(
            "Competenza HACS: Atti, template e catalogo atti. Se la richiesta tocca bozze, modelli o struttura di un atto, "
            "Lex deve selezionare il template piu' vicino dal repository strutturato, evidenziare i dati da completare, "
            "mostrare allegati obbligatori e controlli di conformita' e proporre il prossimo passo redazionale."
        ),
        context_hint=(
            "Per gli atti parti dal modello piu' vicino, poi mostra subito campi guidati, allegati, check e compilatore collegato."
        ),
    ),
    LexCompetenceProfile(
        topic="economico",
        label="Tariffario, preventivi, fatturazione e pagamenti",
        focus_label="economico di studio",
        keywords=(
            "tariffario",
            "onorario",
            "compenso",
            "preventivo",
            "preventivi",
            "incarico",
            "fattura",
            "fatture",
            "fatturazione",
            "parcella",
            "parcelle",
            "pagamento",
            "pagamenti",
            "saldo",
            "notula",
            "sdi",
            "ritenuta",
        ),
        section_titles=("Tariffario", "Preventivi", "Fatturazione", "Clienti"),
        prompt_block=(
            "Competenza HACS: Tariffario, preventivi, fatturazione e pagamenti. Quando il tema e' economico, "
            "Lex deve distinguere bene tra parametro, preventivo, conferimento di incarico, parcella emessa, stato di pagamento "
            "e impatto sul cliente, senza confondere le fasi del flusso. "
            "Sui preventivi deve usare il repository strutturato del wizard: stato del workflow, passo corrente, campi mancanti, "
            "warning operativi, prossima azione, pratica suggerita e canale Studio/Online. "
            "Il calcolo economico resta deterministico nel codice: imponibile, CPA, base IVA, IVA, anticipazioni art. 15 e totale "
            "non vanno mai ricalcolati liberamente dal modello."
        ),
        context_hint=(
            "Per l'area economica chiarisci sempre se stiamo parlando di tariffario, preventivo, conferimento, fattura o pagamento, "
            "e usa sempre step wizard, warning e next action reali del repository preventivi."
        ),
    ),
    LexCompetenceProfile(
        topic="pec_firma_comunicazioni",
        label="PEC, firma e comunicazioni",
        focus_label="PEC, firma digitale e comunicazioni",
        keywords=(
            "pec",
            "firma",
            "firmato",
            "p7m",
            "cades",
            "certificato",
            "token",
            "smart card",
            "ricevuta",
            "cancelleria",
            "notifica pec",
            "comunicazione",
            "messaggio sdi",
        ),
        section_titles=("PEC e canali email", "Impostazioni studio", "Fascicoli"),
        prompt_block=(
            "Competenza HACS: PEC, firma e comunicazioni. Se c'e' un problema tecnico o operativo su PEC, firma digitale o ricevute, "
            "Lex deve indicare prima la causa probabile, poi il primo controllo utile e infine la correzione immediata nel flusso di studio."
        ),
        context_hint=(
            "Per PEC e firma parti da canale, credenziali, certificato, ricevute e collegamento al fascicolo o al deposito."
        ),
    ),
    LexCompetenceProfile(
        topic="ricerca_legale",
        label="Ricerca legale e fonti ufficiali",
        focus_label="ricerca legale aggiornata",
        keywords=(
            "ricerca legale",
            "norma",
            "normativa",
            "legge",
            "decreto",
            "articolo",
            "fonte ufficiale",
            "fonti ufficiali",
            "normattiva",
            "ministero",
            "aggiornamento",
        ),
        section_titles=("Ricerca legale e fonti web", "Archivio sentenze", "Strumenti legali"),
        prompt_block=(
            "Competenza HACS: Ricerca legale e fonti ufficiali. Se la domanda richiede verifica normativa o aggiornamento, "
            "Lex deve distinguere dato certo, fonte ufficiale, ultimo aggiornamento disponibile e limiti del contesto interno. "
            "Per le fonti legali deve usare prima il repository strutturato di motori, fonti, keyword routing, monitoraggio, alert e audit, "
            "e solo dopo lasciare al modello la sintesi della risposta."
        ),
        context_hint=(
            "Quando la richiesta e' normativa o di aggiornamento, passa dal repository legale a fonti ufficiali e web live solo se serve davvero."
        ),
        include_live_web=True,
    ),
    LexCompetenceProfile(
        topic="archivio_sentenze",
        label="Archivio sentenze e giurisprudenza",
        focus_label="pronunce e giurisprudenza rilevanti",
        keywords=(
            "sentenza",
            "sentenze",
            "giurisprudenza",
            "massima",
            "pronuncia",
            "pronunce",
            "cassazione",
            "corte costituzionale",
            "tar",
            "consiglio di stato",
            "provvedimento",
        ),
        section_titles=("Archivio sentenze", "Ricerca legale e fonti web"),
        prompt_block=(
            "Competenza HACS: Archivio sentenze e giurisprudenza. Su sentenze e pronunce Lex deve partire prima dal corpus professionale "
            "verificabile, poi dal repository strutturato di fonti, tassonomia, policy e sync, e solo dopo usare il modello per spiegare la risposta. "
            "Lex puo' citare una pronuncia solo se il riferimento professionale e' verificato e puo' promettere il PDF solo se il corpus lo segnala disponibile. "
            "Chiarisci sempre se stai parlando di sentenza, ordinanza o altro provvedimento."
        ),
        context_hint=(
            "Per la giurisprudenza dai priorita' a corpus verificabile, fonte giusta, organo giudicante, data, principio utile e stato reale del PDF."
        ),
        include_live_web=True,
    ),
    LexCompetenceProfile(
        topic="strumenti_legali",
        label="Strumenti legali e calcoli",
        focus_label="strumenti legali e moduli di calcolo",
        keywords=(
            "strumento legale",
            "strumenti legali",
            "interessi",
            "contributo unificato",
            "ctu",
            "pignoramento",
            "credito",
            "rivalutazione",
            "tfr",
            "usura",
            "successione",
            "danno biologico",
        ),
        section_titles=("Strumenti legali", "Tariffario", "Ricerca legale e fonti web"),
        prompt_block=(
            "Competenza HACS: Strumenti legali e calcoli. Quando la domanda riguarda un calcolo o uno strumento, "
            "Lex deve indicare subito quale modulo usare, quali dati servono e quali verifiche giuridiche o documentali vanno fatte prima del risultato finale."
        ),
        context_hint=(
            "Per i moduli di calcolo chiarisci subito input necessari, risultato atteso e limite consultivo del calcolo."
        ),
    ),
    LexCompetenceProfile(
        topic="applicazioni_moduli",
        label="Applicazioni e moduli del gestionale",
        focus_label="moduli e percorsi del software",
        keywords=(
            "applicazione",
            "applicazioni",
            "modulo",
            "moduli",
            "catalogo",
            "workspace",
            "sezione",
            "dove trovo",
            "come apro",
        ),
        section_titles=("Applicazioni", "Impostazioni studio", "Quadro operativo"),
        prompt_block=(
            "Competenza HACS: Applicazioni e moduli del gestionale. Se l'utente chiede dove si trova una funzione o come raggiungerla, "
            "Lex deve usare il registro workspace del software per indicare modulo corretto, modalita di accesso, percorso e azione successiva, "
            "senza perdersi in spiegazioni teoriche."
        ),
        context_hint=(
            "Quando il tema e' il software stesso, indica il modulo giusto, il percorso, se l'accesso e' diretto o guidato e il passo operativo da fare li'."
        ),
    ),
    LexCompetenceProfile(
        topic="impostazioni_sincronizzazioni",
        label="Impostazioni, sincronizzazioni e configurazione studio",
        focus_label="configurazione studio e sincronizzazioni",
        keywords=(
            "impostazioni",
            "configurazione",
            "configura",
            "studio",
            "sincronizzazione",
            "sincronizza",
            "sync",
            "calendario",
            "google calendar",
            "import",
            "esporta",
            "notifiche",
            "aggiorna il bundle",
        ),
        section_titles=("Impostazioni studio", "PEC e canali email", "Agenda", "Applicazioni"),
        prompt_block=(
            "Competenza HACS: Impostazioni, sincronizzazioni e configurazione studio. Se l'utente chiede setup, sync o configurazioni, "
            "Lex deve distinguere impostazioni di studio, canali email/PEC, calendario e integrazioni, indicando prima cosa verificare e poi cosa salvare o sincronizzare."
        ),
        context_hint=(
            "Per configurazioni e sync orienta la risposta su impostazioni da controllare, stato attuale e prossimo test utile."
        ),
    ),
)


def _score_profile(question: str, profile: LexCompetenceProfile) -> int:
    text = _clean_spaces(question)
    if not text:
        return 0
    score = 0
    for keyword in profile.keywords:
        if _contains_query_token(text, keyword):
            score += 3 if " " in keyword else 1
    return score


def match_competence_profiles(question: str, *, limit: int = 4) -> list[LexCompetenceProfile]:
    clean_question = _clean_spaces(question)
    if not clean_question:
        return []
    scored: list[tuple[int, int, LexCompetenceProfile]] = []
    for index, profile in enumerate(_COMPETENCE_PROFILES):
        score = _score_profile(clean_question, profile)
        if score <= 0:
            continue
        scored.append((score, -index, profile))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [profile for _score, _order, profile in scored[: max(int(limit or 0), 1)]]


def primary_competence_profile(question: str) -> LexCompetenceProfile | None:
    matches = match_competence_profiles(question, limit=1)
    return matches[0] if matches else None


def build_competence_prompt_blocks(question: str, *, limit: int = 4) -> list[str]:
    return [profile.prompt_block for profile in match_competence_profiles(question, limit=limit)]


def build_competence_context_hints(question: str, *, limit: int = 3) -> list[str]:
    return [profile.context_hint for profile in match_competence_profiles(question, limit=limit)]


def resolve_competence_section_titles(question: str, *, limit: int = 3, max_sections: int = 6) -> tuple[str, ...]:
    sections: list[str] = []
    for profile in match_competence_profiles(question, limit=limit):
        for title in profile.section_titles:
            if title in sections:
                continue
            sections.append(title)
            if len(sections) >= max_sections:
                return tuple(sections)
    return tuple(sections)


def resolve_competence_labels(question: str, *, limit: int = 3) -> list[str]:
    return [profile.label for profile in match_competence_profiles(question, limit=limit)]


def build_competence_catalog_prompt() -> str:
    labels = ", ".join(profile.label for profile in _COMPETENCE_PROFILES)
    return (
        "=== COMPETENZE HACS ===\n"
        "Lex copre in modo operativo queste aree del software: "
        f"{labels}.\n"
        "Per ogni richiesta deve scegliere prima la competenza giusta, usare i moduli pertinenti e non allargarsi ad aree non richieste."
    )


__all__ = [
    "LexCompetenceProfile",
    "build_competence_catalog_prompt",
    "build_competence_context_hints",
    "build_competence_prompt_blocks",
    "match_competence_profiles",
    "primary_competence_profile",
    "resolve_competence_labels",
    "resolve_competence_section_titles",
]
