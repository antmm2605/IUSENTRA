"""
Regole di rilevanza per selezionare norme utili a uno studio legale.

Queste regole non sostituiscono l'analisi giuridica: servono a filtrare e
classificare automaticamente gli XML Normattiva prima dell'indicizzazione Lex AI.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TopicMatch:
    topic: str
    score: float
    matched_keywords: list[str]


# Collezioni che conviene tenere anche se il testo non contiene molte keyword.
# Per Lex AI sono fonti fondamentali.
ALWAYS_KEEP_COLLECTIONS = {
    "codici",
    "testi unici",
}

# Keyword volutamente ampie ma orientate al lavoro di uno studio legale.
# Puoi raffinarle nel tempo con log e statistiche reali.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "processo_civile_pct": [
        "codice di procedura civile", "procedura civile", "processo civile",
        "giudice di pace", "tribunale", "corte d'appello", "cassazione civile",
        "decreto ingiuntivo", "procedimento monitorio", "opposizione a decreto ingiuntivo",
        "esecuzione forzata", "pignoramento", "precetto", "sfratto", "convalida di sfratto",
        "polisweb", "pct", "processo civile telematico", "deposito telematico",
        "fascicolo informatico", "contributo unificato", "nota di iscrizione a ruolo",
    ],
    "civile_obbligazioni_contratti": [
        "codice civile", "obbligazioni", "contratti", "responsabilita civile",
        "risarcimento del danno", "inadempimento", "adempimento", "prescrizione",
        "decadenza", "proprieta", "possesso", "usufrutto", "servitu",
    ],
    "famiglia_minori_successioni": [
        "famiglia", "separazione", "divorzio", "unione civile", "convivenza",
        "affidamento", "minori", "responsabilita genitoriale", "assegno di mantenimento",
        "successione", "successioni", "eredita", "testamento", "legittima", "curatore speciale",
    ],
    "lavoro_previdenza": [
        "rapporto di lavoro", "licenziamento", "lavoratore", "datore di lavoro",
        "contratto collettivo", "retribuzione", "mansioni", "previdenza", "inps",
        "inail", "rito del lavoro", "tfr", "contributi previdenziali",
    ],
    "tributario_ptt": [
        "processo tributario", "giustizia tributaria", "ricorso tributario",
        "agenzia delle entrate", "cartella di pagamento", "avviso di accertamento",
        "accertamento tributario", "commissione tributaria", "corte di giustizia tributaria",
        "sigit", "ptt", "tributario", "imposte", "iva", "irpef", "ires", "irap",
    ],
    "amministrativo_pat": [
        "processo amministrativo", "codice del processo amministrativo",
        "tribunale amministrativo regionale", "tar", "consiglio di stato",
        "siga", "pat", "appalti pubblici", "accesso agli atti", "procedimento amministrativo",
        "pubblica amministrazione", "silenzio amministrativo",
    ],
    "penale_pdp": [
        "codice penale", "codice di procedura penale", "processo penale",
        "difensore", "indagini preliminari", "misure cautelari", "querela",
        "pdp", "portale deposito atti penali", "deposito atti penali",
        "imputato", "persona offesa", "udienza preliminare",
    ],
    "telematico_digitale_firma_pec": [
        "firma digitale", "firma elettronica", "pec", "posta elettronica certificata",
        "domicilio digitale", "documento informatico", "conservazione digitale",
        "codice dell'amministrazione digitale", "cad", "spid", "cie", "cns",
        "identita digitale", "notificazione telematica", "notificazioni telematiche",
    ],
    "forense_parametri_deontologia": [
        "avvocato", "avvocati", "professione forense", "ordinamento forense",
        "consiglio nazionale forense", "cnf", "parametri forensi", "compenso professionale",
        "liquidazione compensi", "deontologia", "codice deontologico", "gratuito patrocinio",
        "patrocinio a spese dello stato", "spese di giustizia",
    ],
    "mediazione_adr_negoziazione": [
        "mediazione", "negoziazione assistita", "arbitrato", "conciliazione",
        "organismo di mediazione", "adr", "condizione di procedibilita",
    ],
    "crisi_impresa_societario": [
        "crisi d'impresa", "liquidazione giudiziale", "fallimento", "concordato preventivo",
        "codice della crisi", "societa", "societario", "impresa", "registro delle imprese",
        "amministratore", "assemblea", "bilancio", "responsabilita degli amministratori",
    ],
    "locazioni_condominio": [
        "locazione", "locazioni", "contratto di locazione", "sfratto per morosita",
        "condominio", "condominiale", "amministratore di condominio", "canone", "morosita",
    ],
    "immigrazione_cittadinanza": [
        "immigrazione", "straniero", "stranieri", "permesso di soggiorno",
        "protezione internazionale", "asilo", "cittadinanza", "espulsione",
    ],
    "privacy_gdpr": [
        "protezione dei dati personali", "privacy", "gdpr", "regolamento ue 2016/679",
        "garante per la protezione dei dati", "dati personali", "trattamento dei dati",
    ],
    "unep_notifiche_esecuzioni": [
        "unep", "ufficiale giudiziario", "notifica", "notificazioni", "pignoramento",
        "esecuzione mobiliare", "esecuzione immobiliare", "vendita giudiziaria",
    ],
}

TOPIC_KEYWORDS.update({
    "civile": ["codice civile", "obbligazioni", "contratti", "responsabilita civile", "risarcimento"],
    "processo civile": ["codice di procedura civile", "processo civile", "procedura civile", "citazione", "udienza"],
    "PCT": ["pct", "processo civile telematico", "datiatto", "polisweb", "busta telematica"],
    "famiglia": ["separazione", "divorzio", "minori", "affidamento", "responsabilita genitoriale"],
    "lavoro": ["licenziamento", "rapporto di lavoro", "datore di lavoro", "lavoratore", "tfr"],
    "tributario": ["tributario", "imposte", "iva", "agenzia delle entrate", "sigit", "ptt"],
    "amministrativo": ["tar", "consiglio di stato", "procedimento amministrativo", "pat", "siga"],
    "penale": ["codice penale", "procedura penale", "processo penale", "pdp", "indagini preliminari"],
    "esecuzioni": ["esecuzione forzata", "pignoramento", "precetto", "vendita giudiziaria"],
    "locazioni": ["locazione", "sfratto", "canone", "conduttore", "locatore"],
    "condominio": ["condominio", "amministratore di condominio", "assemblea condominiale"],
    "societario": ["societa", "srl", "spa", "assemblea", "bilancio", "amministratori"],
    "crisi impresa": ["crisi d'impresa", "liquidazione giudiziale", "concordato", "sovraindebitamento"],
    "privacy": ["privacy", "gdpr", "dati personali", "garante per la protezione"],
    "forense/deontologia": ["avvocato", "deontologia", "codice deontologico", "consiglio nazionale forense"],
    "compensi/parametri forensi": ["parametri forensi", "compenso professionale", "dm 55", "onorario"],
    "deposito telematico": ["deposito telematico", "controlli automatici", "punto di accesso"],
    "firma digitale": ["firma digitale", "cades", "pades", "certificato digitale"],
    "PEC/notifiche": ["pec", "posta elettronica certificata", "notifica telematica", "domicilio digitale"],
    "fatturazione": ["fattura", "fatturazione elettronica", "iva", "corrispettivo"],
    "antiriciclaggio": ["antiriciclaggio", "adeguata verifica", "titolare effettivo"],
    "appalti": ["appalto", "contratti pubblici", "anac", "gara"],
    "previdenza": ["inps", "inail", "previdenza", "invalidita civile"],
    "bancario": ["banca", "credito", "mutuo", "usura", "anatocismo"],
    "consumatori": ["consumatore", "codice del consumo", "garanzia legale"],
})


def normalize_text(value: str | None) -> str:
    text = value or ""
    text = text.lower()
    text = text.replace("’", "'").replace("`", "'")
    # Normattiva spesso usa e', perche', responsabilita'. Manteniamo sia forma asciutta sia apostrofi.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9àèéìòù'\s/.-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def collection_is_always_keep(collection_name: str | None) -> bool:
    c = normalize_text(collection_name)
    return any(item in c for item in ALWAYS_KEEP_COLLECTIONS)


def detect_topics(title: str, body: str, *, collection_name: str | None = None) -> list[TopicMatch]:
    title_norm = normalize_text(title)
    body_norm = normalize_text(body)
    matches: list[TopicMatch] = []

    for topic, keywords in TOPIC_KEYWORDS.items():
        score = 0.0
        found: list[str] = []
        for kw in keywords:
            k = normalize_text(kw)
            if not k:
                continue
            in_title = k in title_norm
            in_body = k in body_norm
            if in_title or in_body:
                found.append(kw)
                if in_title:
                    score += 3.0
                if in_body:
                    score += 1.0

        if score > 0:
            matches.append(TopicMatch(topic=topic, score=score, matched_keywords=found[:20]))

    matches.sort(key=lambda x: x.score, reverse=True)

    if not matches and collection_is_always_keep(collection_name):
        matches.append(TopicMatch(topic="fonte_generale_codici_testi_unici", score=3.0, matched_keywords=[collection_name or "collezione fondamentale"]))

    return matches


def relevance_score(matches: Iterable[TopicMatch]) -> float:
    items = list(matches)
    if not items:
        return 0.0
    return round(sum(m.score for m in items), 3)


def topic_names(matches: Iterable[TopicMatch]) -> list[str]:
    return [m.topic for m in matches]
