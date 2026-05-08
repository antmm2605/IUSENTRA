"""Router fonti legali professionale per IUSENTRA Lex.

Estende la selezione delle fonti riconoscendo tutti i domini giuridici
italiani rilevanti per uno studio legale: normativa, giurisprudenza,
tributario, telematico civile/penale/amministrativo/tributario, compensi
forensi, mediazione, PEC e domicili digitali.

Non sostituisce SourceRouter — fornisce un layer di classificazione e
arricchimento fonti che il RetrievalOrchestrator può interrogare per
costruire la lista sorgenti ottimale per ogni richiesta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Pattern di classificazione dominio giuridico
# ---------------------------------------------------------------------------

_NORMATIVA_NAZIONALE_TOKENS = frozenset(
    {
        "norma", "normativa", "legge", "decreto", "d.lgs", "d.l.", "d.p.r.", "l. n.",
        "codice civile", "codice penale", "codice di procedura", "c.c.", "c.p.c.",
        "articolo", "art.", "comma", "gazzetta ufficiale", "normattiva",
        "testo unico", "testo consolidato", "regio decreto", "r.d.",
        "disposizioni attuative", "regolamento",
    }
)

_NORMATIVA_UE_TOKENS = frozenset(
    {
        "regolamento ue", "direttiva ue", "direttiva europea", "eur-lex",
        "gdpr", "dsgvo", "dsa", "dma", "ai act", "corte di giustizia ue",
        "cjeu", "echr", "cedu", "corte europea", "convenzione europea",
        "trattato ue", "tfue", "carta diritti fondamentali ue",
    }
)

_GIURISPRUDENZA_TOKENS = frozenset(
    {
        "sentenza", "ordinanza", "decreto", "massima", "giurisprudenza",
        "cassazione", "corte di cassazione", "cass.", "sezioni unite",
        "corte costituzionale", "corte d'appello", "tribunale", "trib.",
        "giudice di pace", "ecli", "repertorio", "archivio sentenze",
        "principio di diritto", "orientamento", "indirizzo giurisprudenziale",
    }
)

_TRIBUTARIO_TOKENS = frozenset(
    {
        "agenzia entrate", "agenzia delle entrate", "fisco", "iva", "irpef",
        "ires", "irap", "imposta", "tassazione", "accertamento", "avviso",
        "dichiarazione", "modello unico", "ptt", "processo tributario",
        "sigit", "cgt", "commissione tributaria", "giustizia tributaria",
        "finanze", "mef", "credito d'imposta", "deduzione", "detrazione",
        "regime fiscale", "risoluzione", "circolare agenzia", "interpello",
        "ravvedimento", "rimborso", "ricorso tributario",
    }
)

_TELEMATICO_CIVILE_TOKENS = frozenset(
    {
        "pct", "pst", "polisweb", "deposito telematico", "tribunale civile",
        "d.m. 44/2011", "dm 44", "busta telematica", "pec deposito",
        "ricevuta accettazione", "ricevuta consegna", "cancelleria",
        "fascicolo informatico", "ufficio del processo",
    }
)

_TELEMATICO_PENALE_TOKENS = frozenset(
    {
        "pdp", "deposito penale", "processo penale", "d.lgs. 150/2022",
        "riforma cartabia penale", "d.m. 217/2023", "penale telematico",
        "atti penali", "procura penale", "tribunale penale",
    }
)

_TELEMATICO_AMMINISTRATIVO_TOKENS = frozenset(
    {
        "pat", "siga", "tar", "consiglio di stato", "cds",
        "giustizia amministrativa", "ricorso amministrativo",
        "d.p.c.m. 16/02/2016", "codice processo amministrativo", "c.p.a.",
        "appalto", "gara pubblica", "atti amministrativi",
    }
)

_TELEMATICO_TRIBUTARIO_TOKENS = frozenset(
    {
        "ptt", "sigit", "cgt", "ricorso tributario telematico",
        "commissione tributaria", "atti tributari telematici",
    }
)

_COMPENSI_FORENSI_TOKENS = frozenset(
    {
        "compenso forense", "onorario", "parcella", "tariffa", "tariffario",
        "d.m. 55", "dm 55", "d.m. 55/2014", "d.m. 147/2022", "dm 147",
        "cnf tariffe", "art. 13 l. 247", "l. 247/2012",
        "liquidazione compensi", "nota spese", "recupero crediti avvocato",
        "compenso a tempo", "art. 22-bis", "parametri forensi",
    }
)

_MEDIAZIONE_TOKENS = frozenset(
    {
        "mediazione", "mediatore", "procedura mediazione", "d.lgs. 28/2010",
        "d.m. 150/2023", "dm 150", "organismo mediazione",
        "tentativo obbligatorio", "mediazione obbligatoria",
        "accordo mediazione", "verbale mediazione", "mediazione civile",
        "conciliazione", "adr",
    }
)

_PEC_DOMICILIO_DIGITALE_TOKENS = frozenset(
    {
        "pec", "posta elettronica certificata", "domicilio digitale",
        "ini-pec", "ini pec", "ipa", "inad", "indice nazionale domicili",
        "reginde", "notifica telematica", "notifica via pec",
        "comunicazione telematica", "pec avvocato", "pec tribunale",
    }
)

_PENALE_TOKENS = frozenset(
    {
        "penale", "reato", "imputato", "difensore", "pm", "procura",
        "gip", "gup", "udienza preliminare", "patteggiamento",
        "riforma cartabia", "recidiva", "prescrizione penale",
        "querela", "denuncia", "estinzione reato", "amnistia",
        "arresti domiciliari", "misura cautelare", "custodia cautelare",
    }
)

_CIVILE_TOKENS = frozenset(
    {
        "civile", "responsabilità contrattuale", "inadempimento",
        "risoluzione contratto", "risarcimento danni", "danno emergente",
        "lucro cessante", "prescrizione civile", "interruzione prescrizione",
        "ingiunzione", "decreto ingiuntivo", "opposizione", "sfratto",
        "locazione", "condominio", "usufrutto", "successione", "eredità",
    }
)

_FAMIGLIA_TOKENS = frozenset(
    {
        "separazione", "divorzio", "affidamento", "mantenimento figli",
        "assegno divorzile", "unione civile", "convivente", "adozione",
        "minori", "volontaria giurisdizione", "tutela", "curatela",
        "amministrazione sostegno",
    }
)

_LAVORO_TOKENS = frozenset(
    {
        "lavoro", "licenziamento", "contratto lavoro", "ccnl",
        "mobbing", "discriminazione", "inps", "inail", "previdenza",
        "pensione", "tfr", "busta paga", "straordinario",
        "contributi", "ispezione lavoro",
    }
)

_PRIVACY_GDPR_TOKENS = frozenset(
    {
        "gdpr", "privacy", "dati personali", "trattamento dati",
        "garante privacy", "gpdp", "consenso informato", "titolare",
        "responsabile trattamento", "registro trattamenti",
        "data breach", "dpo", "ropa",
    }
)


# ---------------------------------------------------------------------------
# Mapping dominio → fonti ufficiali da includere nel retrieval
# ---------------------------------------------------------------------------

DOMAIN_OFFICIAL_SOURCE_IDS: dict[str, list[str]] = {
    "normativa_nazionale": [
        "normattiva", "gazzetta_ufficiale", "pst_giustizia",
    ],
    "normativa_ue": [
        "eur_lex", "curia",
    ],
    "giurisprudenza": [
        "cassazione", "corte_costituzionale", "giustizia_amministrativa",
    ],
    "tributario": [
        "agenzia_entrate", "normattiva", "gazzetta_ufficiale",
    ],
    "telematico_civile": [
        "pst_giustizia", "normattiva",
    ],
    "telematico_penale": [
        "pst_giustizia", "normattiva",
    ],
    "telematico_amministrativo": [
        "giustizia_amministrativa", "normattiva",
    ],
    "telematico_tributario": [
        "normattiva", "agenzia_entrate",
    ],
    "compensi_forensi": [
        "normattiva", "gazzetta_ufficiale", "cnf",
    ],
    "mediazione": [
        "normattiva", "gazzetta_ufficiale", "registro_mediazione",
    ],
    "pec_domicilio": [
        "pst_giustizia",
    ],
    "penale": [
        "normattiva", "cassazione", "pst_giustizia",
    ],
    "civile": [
        "normattiva", "cassazione",
    ],
    "famiglia": [
        "normattiva", "cassazione",
    ],
    "lavoro": [
        "normattiva", "cassazione",
    ],
    "privacy_gdpr": [
        "normattiva", "eur_lex",
    ],
}

# Keyword legali da NON rimuovere durante la query anonimizzazione
LEGAL_MATTER_KEYWORDS: frozenset[str] = frozenset(
    _NORMATIVA_NAZIONALE_TOKENS
    | _NORMATIVA_UE_TOKENS
    | _GIURISPRUDENZA_TOKENS
    | _TRIBUTARIO_TOKENS
    | _COMPENSI_FORENSI_TOKENS
    | _MEDIAZIONE_TOKENS
    | _CIVILE_TOKENS
    | _FAMIGLIA_TOKENS
    | _LAVORO_TOKENS
)

# Patterns nomi propri: prima lettera maiuscola, >= 3 char, non keyword giuridica
_NAME_PATTERN = re.compile(r"\b([A-ZÀÈÌÒÙ][a-zàèìòù]{2,})\b")


@dataclass
class LegalDomainClassification:
    """Classificazione dominio giuridico di una query."""

    primary_domain: str
    secondary_domains: list[str] = field(default_factory=list)
    official_source_ids: list[str] = field(default_factory=list)
    requires_official_sources: bool = False
    requires_telematic_context: bool = False
    requires_compensi_context: bool = False
    requires_mediazione_context: bool = False
    confidence: float = 0.0
    matched_tokens: list[str] = field(default_factory=list)


def classify_legal_domain(query: str) -> LegalDomainClassification:
    """Classifica il dominio giuridico prevalente di una query.

    Analizza il testo della domanda e identifica il dominio legale primario
    (normativa, giurisprudenza, telematico, ecc.) e i domini secondari.
    """
    lowered = str(query or "").lower()
    scores: dict[str, int] = {}
    all_matched: dict[str, list[str]] = {}

    domain_maps = [
        ("normativa_nazionale", _NORMATIVA_NAZIONALE_TOKENS),
        ("normativa_ue", _NORMATIVA_UE_TOKENS),
        ("giurisprudenza", _GIURISPRUDENZA_TOKENS),
        ("tributario", _TRIBUTARIO_TOKENS),
        ("telematico_civile", _TELEMATICO_CIVILE_TOKENS),
        ("telematico_penale", _TELEMATICO_PENALE_TOKENS),
        ("telematico_amministrativo", _TELEMATICO_AMMINISTRATIVO_TOKENS),
        ("telematico_tributario", _TELEMATICO_TRIBUTARIO_TOKENS),
        ("compensi_forensi", _COMPENSI_FORENSI_TOKENS),
        ("mediazione", _MEDIAZIONE_TOKENS),
        ("pec_domicilio", _PEC_DOMICILIO_DIGITALE_TOKENS),
        ("penale", _PENALE_TOKENS),
        ("civile", _CIVILE_TOKENS),
        ("famiglia", _FAMIGLIA_TOKENS),
        ("lavoro", _LAVORO_TOKENS),
        ("privacy_gdpr", _PRIVACY_GDPR_TOKENS),
    ]

    for domain, tokens in domain_maps:
        matched = [t for t in tokens if t in lowered]
        if matched:
            scores[domain] = len(matched)
            all_matched[domain] = matched

    if not scores:
        return LegalDomainClassification(
            primary_domain="generico",
            confidence=0.1,
        )

    sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_domains[0][0]
    secondary = [d for d, _ in sorted_domains[1:4]]

    source_ids: list[str] = []
    seen: set[str] = set()
    for sid in DOMAIN_OFFICIAL_SOURCE_IDS.get(primary, []):
        if sid not in seen:
            source_ids.append(sid)
            seen.add(sid)
    for domain in secondary[:2]:
        for sid in DOMAIN_OFFICIAL_SOURCE_IDS.get(domain, []):
            if sid not in seen:
                source_ids.append(sid)
                seen.add(sid)

    total_tokens = sum(scores.values())
    confidence = min(0.95, 0.4 + total_tokens * 0.06)

    return LegalDomainClassification(
        primary_domain=primary,
        secondary_domains=secondary,
        official_source_ids=source_ids,
        requires_official_sources=primary in {
            "normativa_nazionale", "normativa_ue", "giurisprudenza",
            "tributario", "telematico_civile", "telematico_penale",
            "telematico_amministrativo", "telematico_tributario",
            "compensi_forensi", "mediazione",
        },
        requires_telematic_context=primary in {
            "telematico_civile", "telematico_penale",
            "telematico_amministrativo", "telematico_tributario",
        },
        requires_compensi_context=(primary == "compensi_forensi"),
        requires_mediazione_context=(primary == "mediazione"),
        confidence=confidence,
        matched_tokens=all_matched.get(primary, []),
    )


def extract_legal_matter_from_query(query: str) -> str:
    """Estrae la materia giuridica da una query rimuovendo potenziali nomi propri.

    Non produce query vuote: se dopo la rimozione resta meno del 30%
    del testo originale, restituisce la query originale con avviso.
    """
    if not query.strip():
        return query

    legal_keywords_lower = LEGAL_MATTER_KEYWORDS

    def _is_legal_keyword(token: str) -> bool:
        return token.lower() in legal_keywords_lower

    cleaned = _NAME_PATTERN.sub(
        lambda m: m.group(0) if _is_legal_keyword(m.group(1)) else "[PARTE]",
        query,
    )

    # Rimuovi pattern RG
    rg_pattern = re.compile(r"\b(?:R\.?G\.?|RG)\s*(?:n\.?)?\s*\d{1,8}/\d{2,4}\b", re.I)
    cleaned = rg_pattern.sub("[RG_OMESSO]", cleaned)

    # Se il risultato è troppo ridotto, restituisci originale
    if len(cleaned.replace("[PARTE]", "").replace("[RG_OMESSO]", "").strip()) < len(query) * 0.3:
        return query

    return cleaned.strip()


def get_source_ids_for_workflow(workflow: str, query: str = "") -> list[str]:
    """Restituisce gli ID fonti ufficiali raccomandati per un dato workflow.

    Combina la classificazione workflow con la classificazione dominio
    della query per produrre una lista ottimale.
    """
    workflow_defaults: dict[str, list[str]] = {
        "normativa": ["normattiva", "gazzetta_ufficiale", "eur_lex"],
        "giurisprudenza": ["cassazione", "corte_costituzionale", "giustizia_amministrativa"],
        "prassi": ["normattiva", "agenzia_entrate", "cnf"],
        "research": ["normattiva", "cassazione", "eur_lex", "gazzetta_ufficiale"],
        "fonti": ["normattiva", "cassazione", "corte_costituzionale", "eur_lex"],
        "telematico": ["pst_giustizia", "normattiva"],
        "telematico_status": ["pst_giustizia"],
        "economico": [],
        "cabina": [],
        "compliance": ["normattiva", "pst_giustizia"],
        "fascicolo": [],
        "udienza": [],
        "atto": ["normattiva"],
        "documento": [],
        "question_answering": [],
        "intelligence": ["normattiva", "cassazione"],
    }

    base = list(workflow_defaults.get(workflow, []))

    if query:
        classification = classify_legal_domain(query)
        for sid in classification.official_source_ids:
            if sid not in base:
                base.append(sid)

    return base


def build_professional_source_context(
    query: str,
    workflow: str,
    *,
    include_telematic: bool = False,
    include_compensi: bool = False,
    include_mediazione: bool = False,
) -> dict[str, Any]:
    """Costruisce il contesto fonti professionale per una richiesta Lex.

    Restituisce un dict con:
    - domain: classificazione dominio
    - source_ids: lista ID fonti raccomandate
    - requires_official_sources: se vero, il retrieval deve includere fonti tier-1
    - coverage_notes: note su copertura e limiti delle fonti
    """
    classification = classify_legal_domain(query)
    source_ids = get_source_ids_for_workflow(workflow, query)

    coverage_notes: list[str] = []

    if classification.requires_telematic_context or include_telematic:
        coverage_notes.append(
            "Workflow telematico: verifica sempre lo stato effettivo sul portale ufficiale "
            "(PST/PDP/PAT) con sessione autenticata."
        )

    if classification.requires_compensi_context or include_compensi:
        coverage_notes.append(
            "Compensi forensi: applica D.M. 55/2014 e D.M. 147/2022 con i parametri "
            "aggiornati dal CNF. Verifica la tabella interna del tariffario studio."
        )

    if classification.requires_mediazione_context or include_mediazione:
        coverage_notes.append(
            "Mediazione: applica D.Lgs. 28/2010 come modificato e D.M. 150/2023 "
            "per i compensi del mediatore. Verifica l'organismo iscritto al registro."
        )

    if classification.primary_domain in {"normativa_ue", "giurisprudenza"} and "eur_lex" not in source_ids:
        source_ids.append("eur_lex")
        coverage_notes.append(
            "Dominio UE/giurisprudenza: include EUR-Lex per normativa e sentenze CGUE."
        )

    if "pec_domicilio" in [classification.primary_domain, *classification.secondary_domains]:
        coverage_notes.append(
            "PEC e domicili digitali: usa ReGINde per PEC tribunali e INI-PEC per "
            "domicili digitali di professionisti e imprese."
        )

    return {
        "domain": classification.primary_domain,
        "secondary_domains": classification.secondary_domains,
        "source_ids": source_ids,
        "requires_official_sources": classification.requires_official_sources,
        "requires_telematic_context": classification.requires_telematic_context,
        "coverage_notes": coverage_notes,
        "domain_confidence": classification.confidence,
        "matched_tokens": classification.matched_tokens,
    }
