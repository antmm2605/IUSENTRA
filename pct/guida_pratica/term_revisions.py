"""Rettifiche normative versionate dei reclami, comuni a guida e importatore.

Conservano le regole precedenti e il motivo; non cambiano i calcoli storici.
La sospensione feriale familiare richiede il presupposto concreto della causa.
"""
from copy import deepcopy

REVISION = "reclami-20261011"
SOURCE = "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.articolo.numero=3&atto.articolo.sottoArticolo=1&atto.articolo.tipoArticolo=0&atto.codiceRedazionale=24G00183&atto.dataPubblicazioneGazzetta=2024-11-11"
CAUTION_SOURCE = "https://www.gazzettaufficiale.it/dettaglio/codici/proceduraCivile/323_1_1"
TRIGGER = "Dalla pronuncia in udienza oppure dalla comunicazione, o dalla notificazione se anteriore"


def family_term():
    return {
        "termine": "Reclamo dei provvedimenti temporanei e urgenti",
        "giorni": 10, "decorrenza": TRIGGER, "natura": "perentorio",
        "norma": "art. 473-bis.24 c.p.c.",
        "criticita": "Verificare l'ammissibilità del provvedimento, la fonte della decorrenza e il regime feriale del procedimento concreto.",
        "ferial_suspension_policy": "manual_review", "suspend_august": False,
        "source_event_options": ["pronuncia_udienza", "comunicazione", "notifica_anteriore"],
        "fonte_verifica": SOURCE, "verified_on": "2026-10-11", "revision": REVISION,
    }


def caution_term():
    return {
        "termine": "Reclamo contro provvedimento cautelare",
        "giorni": 15, "decorrenza": TRIGGER, "natura": "perentorio",
        "norma": "art. 669-terdecies c.p.c.; art. 3 L. 742/1969; art. 92 R.D. 12/1941",
        "criticita": "Identificare il provvedimento e l'evento generatore nella fonte; la data dell'impegno in agenda non è la decorrenza del reclamo.",
        "ferial_suspension_policy": "excluded", "suspend_august": False,
        "source_event_options": ["pronuncia_udienza", "comunicazione", "notifica_anteriore"],
        "fonte_verifica": CAUTION_SOURCE, "verified_on": "2026-10-11", "revision": REVISION,
    }


def revise_item(item):
    """Rettifica soltanto le due procedure identificate, con storico esplicito."""
    code = str(item.get("codice") or item.get("code") or "")
    if code not in {"411003", "014100"}:
        return item
    result = deepcopy(item)
    term = family_term() if code == "411003" else caution_term()
    previous = result.get("termini_processuali", [])
    if previous != [term]:
        history = result.setdefault("term_rules_history", [])
        snapshot = {"reason": "Regola specifica verificata; i termini generici di altri mezzi non governano questo reclamo.",
                    "revision": REVISION, "previous_terms": deepcopy(previous), "source": term["fonte_verifica"]}
        if snapshot not in history:
            history.append(snapshot)
    result["termini_processuali"] = [term]
    result["term_rules_revision"] = {"id": REVISION, "verified_on": "2026-10-11", "source": term["fonte_verifica"]}
    return result


def revise_payload(payload):
    """Applica la rettifica ai record attivi, senza percorrere lo storico."""
    result = dict(payload)
    for key in ("codici_materia",):
        if isinstance(result.get(key), list):
            result[key] = [revise_item(row) if isinstance(row, dict) else row for row in result[key]]
    sections = []
    for original in result.get("sezioni", []):
        section = dict(original) if isinstance(original, dict) else original
        if isinstance(section, dict) and isinstance(section.get("codici_materia"), list):
            section["codici_materia"] = [revise_item(row) if isinstance(row, dict) else row for row in section["codici_materia"]]
        sections.append(section)
    if "sezioni" in result:
        result["sezioni"] = sections
    return result
