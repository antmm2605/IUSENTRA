"""Termini di impugnazione — termine breve e termine lungo a confronto.

Base normativa:
- Art. 325 c.p.c.: termine breve per impugnare, decorrente dalla notificazione
  della sentenza (trenta giorni per l'appello, sessanta per il ricorso per
  cassazione).
- Art. 327, primo comma, c.p.c.: termine lungo di sei mesi dalla pubblicazione
  della sentenza, indipendente dalla notificazione.
- Art. 155 c.p.c. per il computo e le proroghe.
- Art. 1 L. 7 ottobre 1969, n. 742: sospensione di diritto dei termini
  processuali dal 1° al 31 agosto. L'art. 3 della stessa legge esclude dalla
  sospensione, in materia civile, le controversie indicate dagli artt. 429 e
  459 c.p.c.: per quelle il modulo espone l'opzione «sospensione esclusa».

Le durate non sono cablate qui: sono lette dai modelli già versionati in
``pct.termini_processuali`` (``DEFAULT_TEMPLATES``), che restano l'unica fonte
dei termini nel progetto, e il computo passa dal motore dello stesso modulo.

Nota sul termine lungo: il modello del motore lo calcola senza sospensione
feriale. Qui la sospensione è applicata per impostazione predefinita, perché
l'art. 1 L. 742/1969 sospende i termini processuali senza distinguere fra
termine breve e termine lungo e l'art. 3 non lo eccettua; l'utente può
disattivarla con l'apposita opzione. La divergenza è deliberata ed esplicita,
non un effetto collaterale.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from pct.calcolatori._base import clean_text, fmt_date_it, parse_date
from pct.termini_processuali import DEFAULT_TEMPLATES, DeadlineTemplate, ItalianDeadlineCalculator

_MEZZI = {
    "appello": {"label": "Appello", "template_breve": "CIV_APPELLO_BREVE"},
    "cassazione": {"label": "Ricorso per cassazione", "template_breve": "CIV_CASSAZIONE_BREVE"},
}

_TEMPLATE_LUNGO = "CIV_APPELLO_LUNGO"


def _template(codice: str) -> DeadlineTemplate:
    for voce in DEFAULT_TEMPLATES:
        if voce.code == codice:
            return voce
    raise ValueError(f"Modello di termine non disponibile nel motore: {codice}.")


def _scadenza(
    template: DeadlineTemplate,
    partenza,
    *,
    sospensione: bool,
    riferimento: str,
) -> Dict[str, Any]:
    esito = ItalianDeadlineCalculator().calculate_template(
        partenza,
        template,
        case_reference=riferimento,
        overrides={"suspend_august": sospensione},
    )
    effettivo = esito.get("template") or {}
    unita = "mesi" if str(effettivo.get("period_type")) == "months" else "giorni"
    return {
        "iso": str(esito.get("deadline") or ""),
        "scadenza": fmt_date_it(esito.get("deadline")),
        "scadenza_senza_proroghe": fmt_date_it(esito.get("rawDeadline")),
        "durata": f"{effettivo.get('base_value')} {unita}",
        "riferimento_normativo": effettivo.get("reference_law") or template.reference_law,
        "passaggi": [
            {"passaggio": voce.get("label", ""), "data": fmt_date_it(voce.get("date"))}
            for voce in esito.get("steps") or []
        ],
        "fonti": [
            {"title": voce.get("label", ""), "url": voce.get("url", "")}
            for voce in esito.get("legalSources") or []
            if voce.get("url")
        ],
    }


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    mezzo = clean_text(payload.get("imp_mezzo")).lower() or "appello"
    if mezzo not in _MEZZI:
        raise ValueError("Mezzo di impugnazione non riconosciuto.")

    pubblicazione = parse_date(payload.get("imp_data_pubblicazione"))
    if pubblicazione is None:
        raise ValueError(
            "Indica la data di pubblicazione (deposito) della sentenza: è il dies a quo del "
            "termine lungo dell'art. 327 c.p.c."
        )
    notificazione: Optional[Any] = parse_date(payload.get("imp_data_notificazione"))
    if notificazione is not None and notificazione < pubblicazione:
        raise ValueError("La notificazione non può precedere la pubblicazione della sentenza.")

    sospensione_scelta = clean_text(payload.get("imp_sospensione_feriale")).lower() or "applica"
    if sospensione_scelta not in {"applica", "esclusa"}:
        raise ValueError("Opzione di sospensione feriale non riconosciuta.")
    sospensione = sospensione_scelta == "applica"
    riferimento = clean_text(payload.get("imp_riferimento"))

    lungo = _scadenza(
        _template(_TEMPLATE_LUNGO),
        pubblicazione,
        sospensione=sospensione,
        riferimento=riferimento,
    )

    breve: Dict[str, Any] = {}
    if notificazione is not None:
        breve = _scadenza(
            _template(_MEZZI[mezzo]["template_breve"]),
            notificazione,
            sospensione=sospensione,
            riferimento=riferimento,
        )

    if breve and breve["iso"] and lungo["iso"]:
        prevale = "breve" if breve["iso"] <= lungo["iso"] else "lungo"
    else:
        prevale = "lungo"
    scadenza_effettiva = breve["scadenza"] if prevale == "breve" else lungo["scadenza"]

    note: List[str] = [
        f"Mezzo di impugnazione: {_MEZZI[mezzo]['label']}.",
        f"Termine lungo: {lungo['durata']} dalla pubblicazione della sentenza ({lungo['riferimento_normativo']}).",
    ]
    if breve:
        note.append(
            f"Termine breve: {breve['durata']} dalla notificazione della sentenza "
            f"({breve['riferimento_normativo']})."
        )
        note.append(
            "Prevale il termine che scade per primo: qui il termine "
            + ("breve." if prevale == "breve" else "lungo.")
        )
    else:
        note.append(
            "Nessuna notificazione indicata: è calcolato il solo termine lungo. Se la sentenza "
            "viene notificata, decorre il termine breve dell'art. 325 c.p.c."
        )
    if sospensione:
        note.append(
            "Applicata la sospensione feriale dal 1° al 31 agosto (art. 1 L. 742/1969), anche al "
            "termine lungo."
        )
    else:
        note.append(
            "Sospensione feriale esclusa su indicazione dell'utente (art. 3 L. 742/1969 per le "
            "controversie degli artt. 429 e 459 c.p.c.)."
        )

    avvisi: List[str] = [
        "Il modulo calcola i termini ordinari di impugnazione della sentenza civile: non copre le "
        "impugnazioni con termini propri né la sospensione o l'interruzione derivanti da altri "
        "istituti.",
        "Il termine breve decorre dalla notificazione della sentenza alla parte: va verificato che "
        "la notificazione sia valida e rivolta al soggetto corretto.",
        "Il calendario delle festività è quello nazionale versionato nel motore: le festività "
        "patronali locali non sono considerate.",
    ]

    righe: List[Dict[str, Any]] = [
        {
            "termine": "Termine lungo",
            "decorrenza": fmt_date_it(pubblicazione),
            "durata": lungo["durata"],
            "scadenza": lungo["scadenza"],
            "riferimento": lungo["riferimento_normativo"],
        }
    ]
    if breve:
        righe.insert(
            0,
            {
                "termine": "Termine breve",
                "decorrenza": fmt_date_it(notificazione),
                "durata": breve["durata"],
                "scadenza": breve["scadenza"],
                "riferimento": breve["riferimento_normativo"],
            },
        )

    fonti = {voce["url"]: voce for voce in (lungo.get("fonti") or []) + (breve.get("fonti") or [])}

    return {
        "mezzo": mezzo,
        "mezzo_label": _MEZZI[mezzo]["label"],
        "data_pubblicazione": fmt_date_it(pubblicazione),
        "data_notificazione": fmt_date_it(notificazione) if notificazione else "",
        "sospensione_feriale": sospensione,
        "termine_breve": breve.get("scadenza", ""),
        "termine_lungo": lungo["scadenza"],
        "termine_prevalente": prevale,
        "scadenza_effettiva": scadenza_effettiva,
        "termini": righe,
        "passaggi": (breve.get("passaggi") if prevale == "breve" else lungo.get("passaggi")) or [],
        "notes": note,
        "warnings": avvisi,
        "sources": list(fonti.values()),
    }
