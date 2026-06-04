"""Fonti normative ufficiali integrabili nei Template Atti.

Il registro non contiene testo normativo copiato: conserva solo riferimenti,
ambito e URL ufficiali, così Lex e l'editor possono proporre richiami senza
inventare articoli o sostituire la verifica professionale dell'avvocato.
"""
from __future__ import annotations

from typing import Any


LAST_VERIFIED_AT = "2026-06-04"


TEMPLATE_ATTI_LEGAL_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "id": "cc_art_1219_mora",
        "title": "Codice civile - costituzione in mora",
        "source_title": "Codice civile",
        "article": "art. 1219 c.c.",
        "official_url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=042U0262&atto.dataPubblicazioneGazzetta=1942-04-04&tipoDettaglio=vigente",
        "reason_for_application": "Richiamo utile per diffide e messe in mora quando il fascicolo riguarda inadempimento o richiesta di pagamento.",
        "verification_status": "fonte ufficiale consultata",
        "last_verified_at": LAST_VERIFIED_AT,
        "match_terms": ("diffida", "mora", "inadempimento", "pagamento", "sollecito"),
    },
    {
        "id": "cpc_art_167_comparsa",
        "title": "Codice di procedura civile - comparsa di risposta",
        "source_title": "Codice di procedura civile",
        "article": "art. 167 c.p.c.",
        "official_url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente",
        "reason_for_application": "Richiamo utile per comparsa di costituzione e risposta e atti difensivi del convenuto.",
        "verification_status": "fonte ufficiale consultata",
        "last_verified_at": LAST_VERIFIED_AT,
        "match_terms": ("comparsa", "costituzione", "risposta", "convenuto", "civile"),
    },
    {
        "id": "cpc_art_163_citazione",
        "title": "Codice di procedura civile - contenuto dell'atto di citazione",
        "source_title": "Codice di procedura civile",
        "article": "art. 163 c.p.c.",
        "official_url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente",
        "reason_for_application": "Richiamo utile per atti introduttivi civili e controlli redazionali sulla citazione.",
        "verification_status": "fonte ufficiale consultata",
        "last_verified_at": LAST_VERIFIED_AT,
        "match_terms": ("citazione", "atto introduttivo", "civile"),
    },
    {
        "id": "gdpr_art_6_base_giuridica",
        "title": "Regolamento (UE) 2016/679 - liceità del trattamento",
        "source_title": "Regolamento (UE) 2016/679",
        "article": "art. 6 GDPR",
        "official_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/ita",
        "reason_for_application": "Richiamo utile per controlli privacy, basi giuridiche e clausole sul trattamento dei dati personali.",
        "verification_status": "fonte ufficiale UE consultata",
        "last_verified_at": LAST_VERIFIED_AT,
        "match_terms": ("privacy", "gdpr", "dati personali", "base giuridica", "trattamento"),
    },
    {
        "id": "gdpr_art_13_informativa",
        "title": "Regolamento (UE) 2016/679 - informazioni all'interessato",
        "source_title": "Regolamento (UE) 2016/679",
        "article": "art. 13 GDPR",
        "official_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/ita",
        "reason_for_application": "Richiamo utile per informative privacy e clausole da rendere chiare al cliente o all'interessato.",
        "verification_status": "fonte ufficiale UE consultata",
        "last_verified_at": LAST_VERIFIED_AT,
        "match_terms": ("informativa", "privacy", "gdpr", "cliente", "interessato"),
    },
)


def template_atti_sources_for_model(*, model_code: str = "", model_name: str = "", area: str = "") -> list[dict[str, Any]]:
    haystack = " ".join(str(item or "") for item in (model_code, model_name, area)).casefold()
    rows: list[dict[str, Any]] = []
    for source in TEMPLATE_ATTI_LEGAL_SOURCES:
        terms = tuple(str(item).casefold() for item in source.get("match_terms", ()))
        if not terms or any(term in haystack for term in terms):
            row = {key: value for key, value in source.items() if key != "match_terms"}
            row["confidence"] = 0.92
            rows.append(row)
    if rows:
        return rows
    return [{key: value for key, value in TEMPLATE_ATTI_LEGAL_SOURCES[0].items() if key != "match_terms"}]
