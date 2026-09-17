"""Calcolo delle proposte PEC dentro il motore, con prova e senza consegna automatica."""
from __future__ import annotations
from datetime import date
import re
from pct.registro_letture.fatti_repository import Fatto
from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

def scadenza_proposta(termine: dict) -> Fatto | None:
    norma = re.sub(r"[^a-z0-9]", "", str(termine.get("norm_ref") or "").lower())
    if norma != "art127tercpc":
        return None
    template = next(t for t in DEFAULT_TEMPLATES if t.code == "CIV_OPPOSIZIONE_127_TER")
    try:
        dies = date.fromisoformat(str(termine.get("dies_a_quo_date") or "")[:10])
    except ValueError:
        return None
    if termine.get("duration_value") != template.base_value:
        return None
    risultato = ItalianDeadlineCalculator().calculate(
        dies, template.base_value, direction=template.direction,
        template_code=template.code, template_name=template.name,
        period_type=template.period_type, free_term=template.free_term,
        suspend_august=template.suspend_august, ferial_suspension_policy=template.ferial_suspension_policy,
        urgent=template.urgent, reference_law=template.reference_law)
    if not risultato.get("deadline"):
        return None
    return Fatto(categoria="data", campo="scadenza_proposta",
        valore=str(risultato["deadline"]), valore_letto=termine["dies_a_quo_date"],
        etichetta="Eventuale opposizione alla trattazione scritta",
        origine="calcolo_termine", verifica="plausibile",
        contesto="Data calcolata dalla comunicazione; proposta facoltativa, non adempimento omesso.",
        prove=[{"codice":"termine_pec", "esito":"attenzione", "termine_id":termine["id"],
                "decorrenza":dies.isoformat(), "norma":template.reference_law,
                "dettaglio":str(risultato.get("explanation") or ""),
                "passaggi":risultato.get("steps") or []}])
