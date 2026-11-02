"""Dalle voci alle bozze dello scadenziario, senza doppioni e senza scritture silenziose.

Le voci con ``scadenziario`` e una data futura diventano ``TermineProposto``: la stessa
forma delle proposte dei provvedimenti di cancelleria (``TermProposal``) che la pipeline
PEC già trasforma in scadenze in BOZZA (``record_pec_schedule_change_receipt``), con
marcatore per messaggio, riga d'identità e conferma dell'avvocato
(``scadenziario_proposte``). Nessuna scrittura avviene qui.

Doppioni esclusi:

* codici già proposti da un altro percorso della stessa PEC (art. 415, sentenza,
  proponente dei termini legali);
* una scadenza dello stesso fascicolo, stesso giorno e stesso codice già presente in
  qualunque stato (anche scartata: l'avvocato ha deciso);
* per le note ex art. 127-ter, ogni termine equivalente riconosciuto da
  ``pct.note_127_ter.proposta.termine_equivalente`` (anche inserito a mano).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pct.note_127_ter.proposta import CODICE_NOTE_127_TER, termine_equivalente
from pct.pec_change_receipt import date_it
from pct.procedura_fasi.fonti import norme as testo_norme

from .modello import EsitoProvvedimento, Voce

_TERM_MARKER_PREFIX = "PEC_TERMINE_PROPOSTO"


@dataclass(frozen=True)
class TermineProposto:
    """Stessa interfaccia di ``pct.pec_provvedimento_terms.TermProposal``, con regola e orario."""

    code: str
    title: str
    due_date: str
    dies_a_quo: str
    norm: str
    note: str
    perentorio: bool = True
    ora: str = ""
    regola_id: str = ""
    tipo_termine: str = ""
    campi_scadenza: dict[str, Any] = field(default_factory=dict)

    def marker(self, message_id: str) -> str:
        return f"{_TERM_MARKER_PREFIX}:{message_id}:{self.code}"

    def summary(self) -> str:
        ora = f" ore {self.ora}" if self.ora else ""
        return f"{self.title}: entro il {date_it(self.due_date)}{ora} ({self.norm})"


def _testo(oggetto: Any, nome: str) -> str:
    valore = oggetto.get(nome) if isinstance(oggetto, dict) else getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "").strip()


def scadenza_equivalente(scadenze: Iterable[Any], *, fascicolo_id: str, giorno: date, codice: str) -> Any | None:
    if not fascicolo_id:
        return None
    if codice == CODICE_NOTE_127_TER:
        return termine_equivalente(scadenze, fascicolo_id=fascicolo_id, giorno=giorno)
    for voce in scadenze or []:
        if (_testo(voce, "id_fascicolo") == fascicolo_id and _testo(voce, "data_scadenza")[:10] == giorno.isoformat()
                and _testo(voce, "deadline_profile_code").upper() == codice.upper()):
            return voce
    return None


def _nota(voce: Voce) -> str:
    parti = [voce.nota, f"Calcolo: {voce.calcolo}" if voce.calcolo else "",
             f"Dal provvedimento: «{voce.prova}»" if voce.prova else "",
             f"Regola {voce.regola_id}; a carico di: {voce.chi}." if voce.chi else f"Regola {voce.regola_id}."]
    return " ".join(p for p in parti if p)


def termine_proposto(voce: Voce) -> TermineProposto:
    campi = dict(voce.campi_scadenza)
    if voce.id_appuntamento:
        campi.setdefault("id_appuntamento", voce.id_appuntamento)
    if voce.ora and "operational_due_at" not in campi and voce.giorno is not None:
        campi["operational_due_at"] = f"{voce.giorno.isoformat()}T{voce.ora}:00"
    return TermineProposto(
        code=voce.codice, title=voce.titolo, due_date=voce.giorno.isoformat() if voce.giorno else "",
        dies_a_quo=(voce.dies_a_quo or voce.giorno or date.today()).isoformat(), norm=testo_norme(list(voce.norme)) or "provvedimento del giudice",
        note=_nota(voce), perentorio=bool(voce.perentorio), ora=voce.ora, regola_id=voce.regola_id,
        tipo_termine=voce.tipo_termine, campi_scadenza=campi,
    )


def proposte_scadenziario(
    esito: EsitoProvvedimento | None, *, oggi: date, fascicolo_id: str = "", scadenze: Iterable[Any] = (),
    codici_gia_proposti: Iterable[str] = (),
) -> list[TermineProposto]:
    """Le bozze da proporre: voci con data futura, non ancora presidiate nello scadenziario."""
    if esito is None:
        return []
    scadenze = list(scadenze or [])
    esclusi = {str(codice).upper() for codice in codici_gia_proposti if codice}
    proposte: list[TermineProposto] = []
    viste: set[tuple[str, date]] = set()
    for voce in esito.voci:
        if not (voce.scadenziario and voce.genere == "termine" and voce.giorno and voce.codice) or voce.giorno < oggi:
            continue
        if voce.codice.upper() in esclusi or (voce.codice.upper(), voce.giorno) in viste:
            continue
        if scadenza_equivalente(scadenze, fascicolo_id=fascicolo_id, giorno=voce.giorno, codice=voce.codice) is not None:
            continue
        viste.add((voce.codice.upper(), voce.giorno))
        proposte.append(termine_proposto(voce))
    return proposte


__all__ = ["TermineProposto", "proposte_scadenziario", "scadenza_equivalente", "termine_proposto"]
