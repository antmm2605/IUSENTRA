"""Termini proposti per ogni provvedimento comunicato dalla cancelleria (in bozza).

Ogni comunicazione di cancelleria riceve la proposta del termine che il provvedimento
apre, calcolata con il motore deterministico ``pct.termini_processuali``. Le proposte
restano in BOZZA nello scadenziario: l'avvocato le conferma o le scarta (mai fonte unica).

Regole applicate:
- sentenza: impugnazione, termine lungo di sei mesi dalla pubblicazione (art. 327 c.p.c.).
  Il termine breve (30 giorni per l'appello, art. 325 e, nel rito del lavoro, art. 434,
  comma 2, c.p.c.; 60 per il ricorso per cassazione) decorre dalla notificazione e non
  dalla comunicazione di cancelleria (art. 133, comma 2, c.p.c.): resta indicato in nota.
- estinzione: se dichiarata dal giudice monocratico il provvedimento ha natura di sentenza
  ed è appellabile (termine lungo art. 327 c.p.c.); se dichiarata dal giudice istruttore in
  causa collegiale è reclamabile al collegio entro 10 giorni dalla comunicazione
  (artt. 308 e 178, commi 3-5, c.p.c.). Nel rito del lavoro il giudice è monocratico.
- sospensione feriale (1-31 agosto, L. 742/1969): non si applica alle controversie di
  lavoro e previdenza (art. 3 L. 742/1969 e art. 92 R.D. 12/1941).
- opposizione alla trattazione scritta (art. 127-ter c.p.c.): proposta dal proponente dei
  termini legali della pipeline PEC, senza restrizioni aggiuntive.
- designazione del giudice, costituzione di parte, fissazioni: nessun termine automatico
  (le date lette sono già presidiate come udienze o termini).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from pct.pec_change_receipt import CourtCommunication, date_it
from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

TERM_MARKER_PREFIX = "PEC_TERMINE_PROPOSTO"
_TEMPLATES = {template.code: template for template in DEFAULT_TEMPLATES}
_LAVORO_RE = re.compile(r"\bLAV\b|\bLAVORO\b|PREVIDENZ|/LAV\b", re.I)


@dataclass(frozen=True)
class TermProposal:
    code: str
    title: str
    due_date: str
    dies_a_quo: str
    norm: str
    note: str
    perentorio: bool = True

    def marker(self, message_id: str) -> str:
        return f"{TERM_MARKER_PREFIX}:{message_id}:{self.code}"

    def summary(self) -> str:
        return f"{self.title}: entro il {date_it(self.due_date)} ({self.norm})"


def is_labour_matter(*values: Any) -> bool:
    return any(_LAVORO_RE.search(str(value or "")) for value in values)


def _calculate(code: str, dies_a_quo: date, *, labour: bool) -> str:
    template = _TEMPLATES[code]
    overrides = {"suspend_august": False} if labour else {}
    result = ItalianDeadlineCalculator().calculate_template(dies_a_quo, template, overrides=overrides)
    return str(result.get("deadline") or "")


def _ferial_note(labour: bool) -> str:
    if labour:
        return "Sospensione feriale non applicata: controversia di lavoro o previdenza (art. 3 L. 742/1969)."
    return "Sospensione feriale 1-31 agosto applicata (L. 742/1969)."


def propose_terms(comm: CourtCommunication, *, dies_a_quo: date, labour: bool) -> list[TermProposal]:
    """Termini aperti dal provvedimento; ``dies_a_quo`` è la data da cui decorrono (da verificare)."""

    dies_label = date_it(dies_a_quo.isoformat())
    proposals: list[TermProposal] = []
    if comm.kind == "sentenza":
        proposals.append(
            TermProposal(
                code="CIV_APPELLO_LUNGO",
                title="Impugnazione sentenza - termine lungo",
                due_date=_calculate("CIV_APPELLO_LUNGO", dies_a_quo, labour=labour),
                dies_a_quo=dies_a_quo.isoformat(),
                norm="art. 327 c.p.c.",
                note=(
                    f"Sei mesi dalla pubblicazione: calcolati dal {dies_label}, data da verificare sul provvedimento. "
                    "Termine breve: 30 giorni dalla notificazione per l'appello (art. 325; nel rito del lavoro art. 434, "
                    "comma 2, c.p.c.), 60 per il ricorso per cassazione; la comunicazione di cancelleria non lo fa "
                    f"decorrere (art. 133, comma 2, c.p.c.). {_ferial_note(labour)}"
                ),
            )
        )
    elif comm.kind == "estinzione":
        proposals.append(
            TermProposal(
                code="CIV_APPELLO_LUNGO",
                title="Impugnazione del provvedimento di estinzione - termine lungo",
                due_date=_calculate("CIV_APPELLO_LUNGO", dies_a_quo, labour=labour),
                dies_a_quo=dies_a_quo.isoformat(),
                norm="art. 327 c.p.c.",
                note=(
                    "Estinzione dichiarata dal giudice monocratico: provvedimento con natura di sentenza, impugnabile "
                    f"con appello. Sei mesi calcolati dal {dies_label}, da verificare sulla data di pubblicazione. "
                    f"{_ferial_note(labour)}"
                ),
            )
        )
        if not labour:
            from pct.termini_processuali import DeadlineTemplate

            reclamo = DeadlineTemplate(
                code="CIV_RECLAMO_ESTINZIONE_308",
                name="Reclamo al collegio contro l'ordinanza di estinzione",
                base_value=10,
                reference_law="Artt. 308 e 178 c.p.c.",
                suspend_august=True,
            )
            due = ItalianDeadlineCalculator().calculate_template(dies_a_quo, reclamo).get("deadline") or ""
            proposals.append(
                TermProposal(
                    code="CIV_RECLAMO_ESTINZIONE_308",
                    title="Reclamo contro l'ordinanza di estinzione (causa collegiale)",
                    due_date=str(due),
                    dies_a_quo=dies_a_quo.isoformat(),
                    norm="artt. 308 e 178 c.p.c.",
                    note=(
                        "Solo se l'estinzione è dichiarata dal giudice istruttore in causa di competenza collegiale: "
                        f"10 giorni dalla comunicazione (qui dal {dies_label}). Con giudice monocratico vale l'appello. "
                        f"{_ferial_note(False)}"
                    ),
                )
            )
    return [proposal for proposal in proposals if proposal.due_date]
