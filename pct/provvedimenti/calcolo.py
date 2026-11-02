"""Il calcolo delle date resta al motore dei termini (``pct/termini_processuali.py``).

Qui si traduce soltanto la regola (template del motore, oppure giorni o mesi, direzione,
giorni liberi, lettura prudenziale) nella chiamata al calcolatore, con la materia del
rito: nel lavoro e nella previdenza la sospensione feriale non si applica (art. 3
L. 742/1969, art. 92 R.D. 12/1941), nel penale il sabato non proroga (art. 172 c.p.p.).
Il motore restituisce la data, la spiegazione e i passaggi: nessun conto è rifatto qui.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from pct.termini_processuali import DEFAULT_TEMPLATES, LETTURA_PRUDENZIALE, ItalianDeadlineCalculator

_TEMPLATES = {template.code: template for template in DEFAULT_TEMPLATES}
_MATERIA_MOTORE = {"lavoro": "labor", "penale": "penale"}


@dataclass(frozen=True)
class Calcolo:
    giorno: date
    spiegazione: str
    regole_motore: tuple[str, ...]


def calcola(termine: dict[str, Any], dies: date, *, materia: str, giorni_letti: int = 0, liberi_letti: bool = False,
            direzione: str = "") -> Calcolo | None:
    """La scadenza dal giorno di partenza ``dies``; None se la regola non è calcolabile.

    ``giorni_letti``: durata scritta dal giudice nel capo, che prevale su quella di legge.
    """
    calcolatore = ItalianDeadlineCalculator()
    materia_motore = _MATERIA_MOTORE.get(materia, "")
    codice = str(termine.get("template") or "")
    if codice and not giorni_letti:
        template = _TEMPLATES.get(codice)
        if template is None:
            return None
        overrides = {"matter_type": materia_motore} if materia_motore else {}
        esito = calcolatore.calculate_template(dies, template, overrides=overrides)
    else:
        template = _TEMPLATES.get(codice)
        mesi = int(termine.get("mesi") or 0)
        valore = giorni_letti or mesi or int(termine.get("giorni") or (template.base_value if template else 0) or 0)
        if valore <= 0:
            return None
        verso = direzione or str(termine.get("direzione") or (template.direction if template else "forward"))
        metadata = {LETTURA_PRUDENZIALE: True} if termine.get("prudenziale") or (verso == "backward" and not (termine.get("liberi") or liberi_letti)) else {}
        esito = calcolatore.calculate(
            dies, valore, direction=verso,
            period_type="months" if mesi and not giorni_letti else "days",
            free_term=bool(termine.get("liberi") or liberi_letti),
            suspend_august=termine.get("feriale", True) is not False,
            matter_type=materia_motore or "civil", metadata=metadata,
            reference_law=str(template.reference_law if template else ""),
        )
    try:
        giorno = date.fromisoformat(str(esito.get("deadline") or "")[:10])
    except ValueError:
        return None
    return Calcolo(giorno, str(esito.get("explanation") or ""), tuple(esito.get("rulesApplied") or ()))


__all__ = ["Calcolo", "calcola"]
