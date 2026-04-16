from __future__ import annotations

import re
import unicodedata
from typing import Iterable


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s/.-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_any(haystack: str, tokens: Iterable[str]) -> int:
    score = 0
    for token in tokens:
        if _normalize(token) in haystack:
            score += 1
    return score


CLASSIFICATION_RULES = [
    {
        "area": "Amministrativo",
        "branca": "Appalti pubblici",
        "sottobranca": "Accesso agli atti",
        "microtema": "accesso agli atti",
        "tokens": [
            "accesso agli atti",
            "accesso difensivo",
            "ostensione",
            "gara",
            "appalti",
        ],
    },
    {
        "area": "Amministrativo",
        "branca": "Appalti pubblici",
        "sottobranca": "Revisione prezzi",
        "microtema": "revisione prezzi",
        "tokens": [
            "revisione prezzi",
            "riequilibrio",
            "compensazione prezzi",
            "caro materiali",
            "appalti",
        ],
    },
    {
        "area": "Amministrativo",
        "branca": "Appalti pubblici",
        "sottobranca": "Soccorso istruttorio",
        "microtema": "soccorso istruttorio",
        "tokens": ["soccorso istruttorio", "gara", "offerta tecnica", "appalti"],
    },
    {
        "area": "Amministrativo",
        "branca": "Appalti pubblici",
        "sottobranca": "Subappalto",
        "microtema": "subappalto",
        "tokens": ["subappalto", "sub-appalto", "appalti"],
    },
    {
        "area": "Amministrativo",
        "branca": "Immigrazione",
        "sottobranca": "Cittadinanza",
        "microtema": "cittadinanza",
        "tokens": ["cittadinanza", "naturalizzazione", "concessione cittadinanza"],
    },
    {
        "area": "Amministrativo",
        "branca": "Immigrazione",
        "sottobranca": "Permesso di soggiorno",
        "microtema": "permesso di soggiorno",
        "tokens": ["permesso di soggiorno", "questura", "permesso", "immigrazione"],
    },
    {
        "area": "Civile",
        "branca": "Responsabilita civile",
        "sottobranca": "Responsabilita medica",
        "microtema": "responsabilita medica",
        "tokens": ["responsabilita medica", "sanitaria", "medico", "ospedale"],
    },
    {
        "area": "Civile",
        "branca": "Responsabilita civile",
        "sottobranca": "Responsabilita medica",
        "microtema": "consenso informato",
        "tokens": ["consenso informato", "informato", "sanitaria", "medica"],
    },
    {
        "area": "Civile",
        "branca": "Lavoro",
        "sottobranca": "Licenziamento",
        "microtema": "licenziamento",
        "tokens": ["licenziamento", "reintegra", "giusta causa", "giustificato motivo"],
    },
    {
        "area": "Civile",
        "branca": "Bancario e finanziario",
        "sottobranca": "Mutui",
        "microtema": "mutuo",
        "tokens": ["mutuo", "piano di ammortamento", "tasso", "spread"],
    },
    {
        "area": "Civile",
        "branca": "Bancario e finanziario",
        "sottobranca": "Usura",
        "microtema": "usura",
        "tokens": ["usura", "tasso soglia", "interessi usurari"],
    },
    {
        "area": "Tributario",
        "branca": "Riscossione ed esecuzione",
        "sottobranca": "Cartella",
        "microtema": "cartella",
        "tokens": ["cartella", "cartella di pagamento", "agente della riscossione"],
    },
    {
        "area": "Tributario",
        "branca": "Riscossione ed esecuzione",
        "sottobranca": "Estratto di ruolo",
        "microtema": "estratto di ruolo",
        "tokens": ["estratto di ruolo", "ruolo", "riscossione"],
    },
    {
        "area": "Tributario",
        "branca": "Riscossione ed esecuzione",
        "sottobranca": "Prescrizione",
        "microtema": "prescrizione",
        "tokens": ["prescrizione", "cartella", "riscossione", "tribut"],
    },
    {
        "area": "Tributario",
        "branca": "IVA",
        "sottobranca": "Detrazione",
        "microtema": "iva detrazione",
        "tokens": ["iva", "detrazione", "fattura", "operazioni inesistenti"],
    },
    {
        "area": "Penale",
        "branca": "Stupefacenti",
        "sottobranca": "Spaccio",
        "microtema": "spaccio",
        "tokens": ["stupefacenti", "spaccio", "detenzione", "lieve entita"],
    },
    {
        "area": "Penale",
        "branca": "Misure cautelari",
        "sottobranca": "Custodia cautelare",
        "microtema": "custodia cautelare",
        "tokens": ["custodia cautelare", "arresti domiciliari", "esigenze cautelari"],
    },
    {
        "area": "Penale",
        "branca": "Procedura penale",
        "sottobranca": "Impugnazioni",
        "microtema": "impugnazioni penali",
        "tokens": ["appello penale", "ricorso per cassazione penale", "impugnazioni", "nullita"],
    },
    {
        "area": "Costituzionale",
        "branca": "Processo costituzionale",
        "sottobranca": "Incidente di costituzionalita",
        "microtema": "incidente di costituzionalita",
        "tokens": ["legittimita costituzionale", "incidente", "questione di costituzionalita"],
    },
    {
        "area": "UE / CEDU",
        "branca": "Appalti",
        "sottobranca": "Affidamenti",
        "microtema": "appalti ue",
        "tokens": ["curia", "public procurement", "appalti", "affidamenti"],
    },
    {
        "area": "UE / CEDU",
        "branca": "Equo processo",
        "sottobranca": "Ragionevole durata",
        "microtema": "equo processo",
        "tokens": ["equa riparazione", "ragionevole durata", "art. 6 cedu", "fair trial"],
    },
    {
        "area": "UE / CEDU",
        "branca": "Vita privata e familiare",
        "sottobranca": "Art. 8 CEDU",
        "microtema": "art 8 cedu",
        "tokens": ["art. 8", "art 8 cedu", "vita privata", "vita familiare"],
    },
    {
        "area": "Contabile",
        "branca": "Responsabilita amministrativa",
        "sottobranca": "Danno erariale",
        "microtema": "danno erariale",
        "tokens": ["danno erariale", "responsabilita amministrativa", "colpa grave"],
    },
]


SOURCE_DEFAULTS = {
    "openga": {"area": "Amministrativo", "giurisdizione": "Amministrativa"},
    "giustizia_amministrativa": {"area": "Amministrativo", "giurisdizione": "Amministrativa"},
    "merito_civile_bdp": {"area": "Civile", "giurisdizione": "Ordinaria"},
    "giustizia_tributaria": {"area": "Tributario", "giurisdizione": "Tributaria"},
    "corte_costituzionale": {"area": "Costituzionale", "giurisdizione": "Costituzionale"},
    "curia": {"area": "UE / CEDU", "giurisdizione": "UE / CEDU"},
    "hudoc": {"area": "UE / CEDU", "giurisdizione": "UE / CEDU"},
    "corte_conti": {"area": "Contabile", "giurisdizione": "Contabile"},
}


AREA_FALLBACK_BRANCH = {
    "Amministrativo": ("Processo amministrativo", "Ottemperanza"),
    "Tributario": ("Processo tributario", "Appello"),
    "Costituzionale": ("Processo costituzionale", "Incidente di costituzionalita"),
    "UE / CEDU": ("Equo processo", "Ragionevole durata"),
    "Contabile": ("Responsabilita amministrativa", "Danno erariale"),
}


def suggest_giurisprudenza_classification(
    *,
    source_id: str = "",
    source_area: str = "",
    source_giurisdizione: str = "",
    source_name: str = "",
    title: str = "",
    abstract: str = "",
    massima: str = "",
    principio_diritto: str = "",
    text_original: str = "",
    materia: str = "",
    rito: str = "",
    organo_giudicante: str = "",
    keywords: Iterable[str] | None = None,
) -> dict[str, str]:
    haystack = _normalize(
        " ".join(
            item
            for item in [
                title,
                abstract,
                massima,
                principio_diritto,
                text_original,
                materia,
                rito,
                organo_giudicante,
                source_name,
                " ".join(list(keywords or [])),
            ]
            if str(item or "").strip()
        )
    )

    result: dict[str, str] = {}
    source_defaults = SOURCE_DEFAULTS.get(str(source_id or "").strip(), {})
    area_hint = str(source_area or source_defaults.get("area") or "").strip()
    giurisdizione_hint = str(source_giurisdizione or source_defaults.get("giurisdizione") or "").strip()

    if area_hint:
        result["area"] = area_hint
    if giurisdizione_hint:
        result["giurisdizione"] = giurisdizione_hint

    if "cassazione" in haystack and "penal" in haystack:
        result.setdefault("area", "Penale")
        result.setdefault("giurisdizione", "Ordinaria")
    elif "cassazione" in haystack and not result.get("area"):
        result["area"] = "Civile"
        result.setdefault("giurisdizione", "Ordinaria")

    best_rule: dict[str, str] | None = None
    best_score = 0
    for rule in CLASSIFICATION_RULES:
        score = _contains_any(haystack, rule["tokens"])
        if score <= 0:
            continue
        if result.get("area") and result["area"] == rule["area"]:
            score += 2
        if materia and _normalize(materia) in haystack:
            score += 1
        if score > best_score:
            best_score = score
            best_rule = rule

    if best_rule:
        result["area"] = best_rule["area"]
        result["branca"] = best_rule["branca"]
        result["sottobranca"] = best_rule["sottobranca"]
        result["microtema"] = best_rule["microtema"]
    elif result.get("area") in AREA_FALLBACK_BRANCH:
        branca, sottobranca = AREA_FALLBACK_BRANCH[result["area"]]
        result.setdefault("branca", branca)
        result.setdefault("sottobranca", sottobranca)

    if not result.get("microtema") and result.get("sottobranca"):
        result["microtema"] = result["sottobranca"].lower()
    return result


def apply_suggested_classification(
    payload: dict[str, object],
    suggestion: dict[str, str],
    *,
    prefer_existing: bool = True,
) -> dict[str, object]:
    updated = dict(payload)
    for key, value in suggestion.items():
        if not value:
            continue
        if prefer_existing and str(updated.get(key) or "").strip():
            continue
        updated[key] = value
    return updated


__all__ = [
    "apply_suggested_classification",
    "suggest_giurisprudenza_classification",
]
