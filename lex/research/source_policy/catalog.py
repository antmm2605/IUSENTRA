"""Catalogo policy e keyword del sistema fonti Lex."""

from __future__ import annotations


SOURCE_POLICIES: dict[str, dict[str, list[str]]] = {
    "normativa": {
        "tier_1": ["normattiva.it", "gazzettaufficiale.it", "eur-lex.europa.eu", "giustizia.it", "giustizia-amministrativa.it", "cortecostituzionale.it", "cortedicassazione.it"],
        "tier_2": ["altalex.com", "brocardi.it", "diritto.it", "federalismi.it", "giustiziainsieme.it", "ilcivilista.it", "ilfamiliarista.it", "quotidianogiuridico.it"],
        "tier_3": ["wikipedia.org", "studiolegale-*.*", "*.substack.com", "*.medium.com", "*.blogspot.com"],
    },
    "giurisprudenza": {
        "tier_1": ["cortecostituzionale.it", "cortedicassazione.it", "giustizia-amministrativa.it", "eur-lex.europa.eu", "giustizia.it", "italgiure.giustizia.it"],
        "tier_2": ["dejure.it", "onelegale.wolterskluwer.it", "ilcaso.it", "giustiziainsieme.it", "federalismi.it", "altalex.com", "quotidianogiuridico.it"],
        "tier_3": ["forum.*", "*.blogspot.com", "*.wordpress.com", "*.medium.com"],
    },
    "tributario": {
        "tier_1": ["agenziaentrate.gov.it", "agenziaentrate.it", "finanze.gov.it", "normattiva.it", "gazzettaufficiale.it", "eur-lex.europa.eu", "giustizia-tributaria.it"],
        "tier_2": ["fiscooggi.it", "eutekne.info", "ipsoa.it", "commercialistatelematico.com", "quotidianopiu.ilsole24ore.com", "ntplusfisco.ilsole24ore.com"],
        "tier_3": ["*.blogspot.com", "*.wordpress.com", "*.substack.com", "forum.*"],
    },
    "lavoro": {
        "tier_1": ["lavoro.gov.it", "ispettorato.gov.it", "inps.it", "inail.it", "normattiva.it", "gazzettaufficiale.it", "eur-lex.europa.eu", "giustizia.it"],
        "tier_2": ["dottrinalavoro.it", "ipsoa.it", "altalex.com", "quotidianolavoro.ilsole24ore.com", "ntpluslavoro.ilsole24ore.com"],
        "tier_3": ["*.blogspot.com", "*.wordpress.com", "forum.*"],
    },
    "previdenza": {
        "tier_1": ["inps.it", "inail.it", "lavoro.gov.it", "normattiva.it", "gazzettaufficiale.it", "eur-lex.europa.eu"],
        "tier_2": ["ipsoa.it", "dottrinalavoro.it", "altalex.com", "quotidianolavoro.ilsole24ore.com"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "privacy": {
        "tier_1": ["garanteprivacy.it", "gpdp.it", "eur-lex.europa.eu", "edpb.europa.eu", "normattiva.it", "gazzettaufficiale.it", "giustizia.it"],
        "tier_2": ["altalex.com", "agenda-digitale.eu", "cybersecurity360.it", "ntplusdiritto.ilsole24ore.com", "ipsoa.it"],
        "tier_3": ["*.medium.com", "*.substack.com", "*.blogspot.com"],
    },
    "societario": {
        "tier_1": ["normattiva.it", "gazzettaufficiale.it", "consob.it", "bancaditalia.it", "eur-lex.europa.eu", "registroimprese.it", "mimit.gov.it", "mise.gov.it"],
        "tier_2": ["dirittobancario.it", "eutekne.info", "ipsoa.it", "ilsocietario.it", "ntplusdiritto.ilsole24ore.com"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "bancario_finanziario": {
        "tier_1": ["bancaditalia.it", "consob.it", "ivass.it", "eur-lex.europa.eu", "normattiva.it", "gazzettaufficiale.it", "esma.europa.eu", "eba.europa.eu"],
        "tier_2": ["dirittobancario.it", "ipsoa.it", "ntplusdiritto.ilsole24ore.com", "altalex.com"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "assicurativo": {
        "tier_1": ["ivass.it", "consob.it", "eur-lex.europa.eu", "normattiva.it", "gazzettaufficiale.it", "giustizia.it"],
        "tier_2": ["dirittobancario.it", "ipsoa.it", "altalex.com", "ntplusdiritto.ilsole24ore.com"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "amministrativo": {
        "tier_1": ["giustizia-amministrativa.it", "normattiva.it", "gazzettaufficiale.it", "giustizia.it", "eur-lex.europa.eu", "anticorruzione.it", "agid.gov.it"],
        "tier_2": ["federalismi.it", "giustiziainsieme.it", "lexitalia.it", "altalex.com", "quotidianogiuridico.it"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "appalti": {
        "tier_1": ["anticorruzione.it", "mit.gov.it", "serviziocontrattipubblici.it", "giustizia-amministrativa.it", "eur-lex.europa.eu", "normattiva.it", "gazzettaufficiale.it"],
        "tier_2": ["appaltiecontratti.it", "federalismi.it", "altalex.com", "ntplusdiritto.ilsole24ore.com"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "penale": {
        "tier_1": ["normattiva.it", "gazzettaufficiale.it", "giustizia.it", "cortedicassazione.it", "cortecostituzionale.it", "eur-lex.europa.eu"],
        "tier_2": ["sistemapenale.it", "penaledp.it", "archiviopenale.it", "altalex.com", "quotidianogiuridico.it"],
        "tier_3": ["*.blogspot.com", "forum.*", "*.youtube.com"],
    },
    "civile": {
        "tier_1": ["normattiva.it", "gazzettaufficiale.it", "giustizia.it", "cortedicassazione.it", "cortecostituzionale.it", "eur-lex.europa.eu"],
        "tier_2": ["ilcaso.it", "altalex.com", "brocardi.it", "ilcivilista.it", "quotidianogiuridico.it"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "famiglia": {
        "tier_1": ["normattiva.it", "gazzettaufficiale.it", "giustizia.it", "cortedicassazione.it", "cortecostituzionale.it", "eur-lex.europa.eu"],
        "tier_2": ["ilfamiliarista.it", "altalex.com", "brocardi.it", "quotidianogiuridico.it"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "immigrazione": {
        "tier_1": ["interno.gov.it", "lavoro.gov.it", "giustizia.it", "eur-lex.europa.eu", "normattiva.it", "gazzettaufficiale.it"],
        "tier_2": ["asgi.it", "altalex.com", "quotidianogiuridico.it"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "fallimentare_crisi_impresa": {
        "tier_1": ["normattiva.it", "gazzettaufficiale.it", "giustizia.it", "cortedicassazione.it", "eur-lex.europa.eu"],
        "tier_2": ["ilcaso.it", "dirittodellacrisi.it", "altalex.com", "ipsoa.it"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "consumatori": {
        "tier_1": ["agcm.it", "mimit.gov.it", "eur-lex.europa.eu", "normattiva.it", "gazzettaufficiale.it", "giustizia.it"],
        "tier_2": ["altalex.com", "ipsoa.it", "ntplusdiritto.ilsole24ore.com"],
        "tier_3": ["*.blogspot.com", "forum.*"],
    },
    "digitale_cyber": {
        "tier_1": ["acn.gov.it", "agid.gov.it", "garanteprivacy.it", "eur-lex.europa.eu", "normattiva.it", "gazzettaufficiale.it"],
        "tier_2": ["cybersecurity360.it", "agenda-digitale.eu", "altalex.com", "ntplusdiritto.ilsole24ore.com"],
        "tier_3": ["*.medium.com", "*.substack.com", "*.blogspot.com"],
    },
    "ue": {
        "tier_1": ["eur-lex.europa.eu", "curia.europa.eu", "europa.eu", "edpb.europa.eu", "esma.europa.eu", "eba.europa.eu", "eiopa.europa.eu"],
        "tier_2": ["europeanlawblog.eu", "altalex.com", "federalismi.it", "dirittounioneuropea.eu"],
        "tier_3": ["*.medium.com", "*.substack.com", "forum.*"],
    },
    "default": {
        "tier_1": ["normattiva.it", "gazzettaufficiale.it", "eur-lex.europa.eu", "giustizia.it", "cortecostituzionale.it", "cortedicassazione.it", "giustizia-amministrativa.it"],
        "tier_2": ["altalex.com", "brocardi.it", "ipsoa.it", "quotidianogiuridico.it", "ntplusdiritto.ilsole24ore.com"],
        "tier_3": ["*.blogspot.com", "*.wordpress.com", "*.medium.com", "*.substack.com", "forum.*"],
    },
}

AREA_KEYWORDS: dict[str, list[str]] = {
    "normativa": ["legge", "decreto", "regolamento", "norma", "codice", "gazzetta ufficiale", "normattiva", "testo unico", "articolo", "comma"],
    "giurisprudenza": ["sentenza", "ordinanza", "massima", "cassazione", "corte costituzionale", "giurisprudenza", "precedente", "sezioni unite", "ricorso", "impugnazione"],
    "tributario": ["fisco", "tasse", "imposta", "iva", "irpef", "ires", "agenzia entrate", "accertamento", "ravvedimento", "compensazione", "ruolo", "diritto tributario"],
    "lavoro": ["licenziamento", "contratto lavoro", "ccnl", "ferie", "malattia", "inps", "ispettorato lavoro", "dimissioni", "smart working", "tfr"],
    "previdenza": ["pensione", "contributi", "inps", "inail", "assegno", "quota 100", "ape sociale", "pensione anticipata"],
    "privacy": ["gdpr", "privacy", "dati personali", "garante privacy", "consenso", "trattamento dati", "dpo", "diritto all'oblio"],
    "societario": ["societa", "srl", "spa", "amministratore", "assemblea", "bilancio", "consob", "registro imprese", "statuto", "quote"],
    "bancario_finanziario": ["banca", "finanza", "consob", "bancaditalia", "mifid", "mutuo", "finanziamento", "tub", "credito"],
    "assicurativo": ["assicurazione", "polizza", "sinistro", "ivass", "rc auto", "indennizzo", "franchigia", "premio"],
    "amministrativo": ["tar", "consiglio di stato", "provvedimento", "accesso atti", "silenzio assenso", "procedimento amministrativo", "autotutela", "interesse legittimo", "codice processo amministrativo", "procedura amministrativa"],
    "appalti": ["appalto", "gara", "codice appalti", "anac", "aggiudicazione", "contratto pubblico", "cig", "consip", "dgue"],
    "penale": ["reato", "penale", "imputato", "processo penale", "misure cautelari", "codice penale", "codice procedura penale", "procura", "patteggiamento"],
    "civile": ["responsabilita civile", "responsabilita", "risarcimento", "danno", "contratto", "contratti", "obbligazioni", "proprieta", "codice civile", "codice procedura civile", "procedura civile", "notifica", "pec", "onere della prova", "nullita", "termini processuali", "decreto ingiuntivo", "opposizione istat", "condominio", "codice della strada", "circolazione stradale", "compenso", "usucapione", "successione"],
    "famiglia": ["divorzio", "separazione", "affido", "mantenimento", "assegno mantenimento", "figli", "diritto di famiglia", "matrimonio", "minori", "adozione"],
    "immigrazione": ["permesso soggiorno", "cittadinanza", "espulsione", "asilo", "straniero", "questura", "ricongiungimento familiare", "decreto flussi"],
    "fallimentare_crisi_impresa": ["fallimento", "concordato", "crisi impresa", "liquidazione", "ccii", "sovraindebitamento", "composizione negoziata"],
    "consumatori": ["consumatore", "clausola vessatoria", "recesso", "agcm", "tutela consumatore", "difetto di conformita", "codice del consumo"],
    "digitale_cyber": ["cybersecurity", "firma digitale", "pec", "acn", "agid", "ai act", "digital services act", "spid", "cie"],
    "ue": ["direttiva ue", "regolamento ue", "corte giustizia ue", "mercato interno", "eur-lex", "trattato", "schengen"],
}

SOURCE_WEIGHTS: dict[str, float] = {
    "tier_1": 1.0,
    "tier_2": 0.72,
    "tier_3": 0.32,
    "unknown": 0.08,
}

MODE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "strict": {"tier_1": 1.0, "tier_2": 0.0, "tier_3": 0.0, "unknown": 0.0},
    "balanced": {"tier_1": 1.0, "tier_2": 0.82, "tier_3": 0.0, "unknown": 0.0},
    "broad": {"tier_1": 1.0, "tier_2": 0.9, "tier_3": 0.55, "unknown": 0.15},
}

RELIABILITY_THRESHOLDS = {"high": 0.78, "medium": 0.42}

__all__ = [
    "AREA_KEYWORDS",
    "MODE_MULTIPLIERS",
    "RELIABILITY_THRESHOLDS",
    "SOURCE_POLICIES",
    "SOURCE_WEIGHTS",
]
