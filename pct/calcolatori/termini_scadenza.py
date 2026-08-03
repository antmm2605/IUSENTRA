"""Termini processuali — scadenza con computo e sospensione feriale.

Base normativa:
- Art. 155 c.p.c.: computo dei termini, esclusione del dies a quo, proroga della
  scadenza che cade in giorno festivo e proroga del termine a giorni che scade
  di sabato per gli atti processuali svolti fuori udienza.
- L. 7 ottobre 1969, n. 742: sospensione feriale dei termini processuali dal
  1° al 31 agosto di ciascun anno.
- Riferimento normativo proprio di ciascun termine (artt. 325, 327, 641, 171-ter
  c.p.c. e le altre norme dichiarate nei modelli).

Il modulo non riscrive le regole di computo: riusa il motore già versionato in
``pct.termini_processuali`` (``ItalianDeadlineCalculator``, ruleset e calendario
delle festività dichiarati), che è la fonte unica dei termini nel progetto, e ne
espone l'esito nel formato della suite Strumenti Forensi. I modelli disponibili
sono quelli di ``DEFAULT_TEMPLATES``: nessun termine nuovo viene introdotto qui.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, fmt_date_it, parse_date, safe_bool, safe_int
from pct.termini_processuali import (
    DEFAULT_TEMPLATES,
    DeadlineTemplate,
    ItalianDeadlineCalculator,
)

_DIREZIONI = {
    "forward": "In avanti dall'evento",
    "backward": "A ritroso dall'udienza o dalla data di riferimento",
}


def modelli() -> List[Dict[str, str]]:
    """Elenco dei modelli di termine, per la select dello strumento."""

    voci: List[Dict[str, str]] = []
    for template in DEFAULT_TEMPLATES:
        etichetta = template.name
        if template.reference_law:
            etichetta = f"{template.name} — {template.reference_law}"
        voci.append({"value": template.code, "label": etichetta})
    return voci


def _template(codice: str) -> DeadlineTemplate:
    for template in DEFAULT_TEMPLATES:
        if template.code == codice:
            return template
    raise ValueError("Modello di termine non riconosciuto.")


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    codice = clean_text(payload.get("term_modello")) or "CIV_APPELLO_BREVE"
    template = _template(codice)

    evento = parse_date(payload.get("term_data_evento"))
    if evento is None:
        raise ValueError(
            "Indica la data dell'evento che fa decorrere il termine "
            "(notifica, deposito, udienza a seconda del modello)."
        )

    urgente = safe_bool(payload.get("term_urgente"))
    valore = safe_int(payload.get("term_valore_personalizzato"))
    if valore < 0:
        raise ValueError("La durata personalizzata non può essere negativa.")

    overrides: Dict[str, Any] = {}
    if urgente:
        overrides["urgent"] = True
    if valore > 0:
        overrides["base_value"] = valore

    esito = ItalianDeadlineCalculator().calculate_template(
        evento,
        template,
        case_reference=clean_text(payload.get("term_riferimento")),
        overrides=overrides,
    )

    effettivo = esito.get("template") or {}
    durata = int(effettivo.get("base_value") or template.base_value)
    unita = "mesi" if str(effettivo.get("period_type")) == "months" else "giorni"

    passaggi = [
        {
            "passaggio": voce.get("label", ""),
            "data": fmt_date_it(voce.get("date")),
            "codice": voce.get("code", ""),
        }
        for voce in esito.get("steps") or []
    ]

    note: List[str] = [esito.get("explanation", "")]
    note.append(
        f"Modello applicato: {effettivo.get('name') or template.name}"
        + (f" ({effettivo.get('reference_law') or template.reference_law})." if template.reference_law else ".")
    )
    if valore > 0:
        note.append(
            f"Durata personalizzata: {durata} {unita} al posto del valore predefinito del modello."
        )

    avvisi: List[str] = []
    if esito.get("requiresLegalReview"):
        avvisi.append(
            "Il motore segnala che il termine richiede verifica professionale: calcolo a ritroso, "
            "termine libero, materia urgente o regime di sospensione feriale non automatico."
        )
    if urgente:
        avvisi.append(
            "Materia urgente: la sospensione feriale non è stata applicata. Va verificato che il "
            "procedimento rientri effettivamente tra quelli sottratti alla L. 742/1969."
        )
    avvisi.append(
        "Il calendario delle festività è quello nazionale versionato nel motore: le festività "
        "patronali locali non sono considerate."
    )

    return {
        "modello": codice,
        "modello_label": effettivo.get("name") or template.name,
        "riferimento_normativo": effettivo.get("reference_law") or template.reference_law,
        "data_evento": fmt_date_it(evento),
        "durata": durata,
        "unita": unita,
        "direzione": _DIREZIONI.get(str(effettivo.get("direction")), str(effettivo.get("direction") or "")),
        "sospensione_feriale": bool(effettivo.get("suspend_august")) and not urgente,
        "termine_libero": bool(effettivo.get("free_term")),
        "scadenza": fmt_date_it(esito.get("deadline")),
        "scadenza_senza_proroghe": fmt_date_it(esito.get("rawDeadline")),
        "affidabilita": esito.get("confidence", ""),
        "richiede_verifica": bool(esito.get("requiresLegalReview")),
        "regole_applicate": ", ".join(esito.get("rulesApplied") or []),
        "versione_regole": esito.get("rulesetVersion", ""),
        "versione_calendario": esito.get("calendarVersion", ""),
        "passaggi": passaggi,
        "notes": [nota for nota in note if nota],
        "warnings": avvisi,
        "sources": [
            {"title": voce.get("label", ""), "url": voce.get("url", "")}
            for voce in esito.get("legalSources") or []
            if voce.get("url")
        ],
    }
