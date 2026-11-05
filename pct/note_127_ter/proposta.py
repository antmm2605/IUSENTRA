"""Il termine perentorio per le note scritte, proposto in bozza (art. 127-ter c.p.c.).

Il decreto assegna «termine perentorio sino alla data della predetta udienza»: il giorno di
scadenza è considerato data di udienza (art. 127-ter, comma 1, c.p.c.). La proposta entra
nello scadenziario in BOZZA, con il meccanismo di conferma già usato per i provvedimenti di
cancelleria: è un termine futuro che cambia lo scadenziario, quindi lo conferma l'avvocato.

Orario: se il decreto invita al deposito «entro le ore 9.30 del giorno di scadenza» la
scadenza operativa è alle 09:30; altrimenti è la fine del giorno, perché il deposito
telematico è tempestivo se la conferma della trasmissione è generata entro la fine del
giorno di scadenza (art. 196-sexies disp. att. c.p.c.; art. 13 D.M. 44/2011).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from pct.pec_change_receipt import date_it

from .decreto import DecretoNoteScritte

CODICE_NOTE_127_TER = "NOTE_127_TER"
TITOLO_NOTE_127_TER = "Deposito note scritte ex art. 127-ter c.p.c."
NORMA_NOTE_127_TER = "art. 127-ter c.p.c."
#: modalità d'udienza già usata dalla pipeline PEC per la trattazione scritta
MODALITA_NOTE_SCRITTE = "note_scritte"
FINE_GIORNO = "23:59"
_TERM_MARKER_PREFIX = "PEC_TERMINE_PROPOSTO"
#: profilo della scadenza operativa creata in automatico dal presidio PEC (pct.pec_pipeline)
PRESIDIO_OPERATIVO = "PEC_AUTO_PRESIDIO"
_RE_NOTE_SCRITTE = re.compile(r"\bnote\b.*(?:127\s*[-\s]?\s*ter|scritt|sostituzion|trattazione)", re.I)


@dataclass(frozen=True)
class PropostaNote:
    """Stessa forma delle proposte di ``pct.pec_provvedimento_terms.TermProposal``, con l'orario."""

    code: str
    title: str
    due_date: str
    dies_a_quo: str
    norm: str
    note: str
    perentorio: bool = True
    ora: str = FINE_GIORNO
    id_appuntamento: str = ""
    campi_scadenza: dict[str, Any] = field(default_factory=dict)
    tipo_termine: str = "TERMINE_PERENTORIO"

    def marker(self, message_id: str) -> str:
        return f"{_TERM_MARKER_PREFIX}:{message_id}:{self.code}"

    def summary(self) -> str:
        return f"{self.title}: entro il {date_it(self.due_date)} ore {self.ora} ({self.norm})"


def proposta_note(
    decreto: DecretoNoteScritte, giorno: date, *, comunicata_il: date | None = None, id_appuntamento: str = "", fonte: str = "",
) -> PropostaNote:
    """La bozza del termine per le note alla data dell'udienza sostituita; decorre dalla comunicazione."""
    ora = decreto.ora_limite or FINE_GIORNO
    orario = (
        f"deposito entro le ore {ora}, come invita il decreto per i tempi di lavorazione della cancelleria"
        if decreto.ora_limite
        else "deposito entro la fine del giorno di scadenza (art. 196-sexies disp. att. c.p.c.)"
    )
    nota = (
        f"Il decreto sostituisce l'udienza già fissata del {giorno:%d/%m/%Y} con note scritte e assegna termine "
        f"perentorio sino a quella data, che vale come data di udienza (art. 127-ter c.p.c.): {orario}. "
        "Data presa dall'udienza del fascicolo: verificarla prima di confermare. Il deposito resta un atto "
        "dell'avvocato, con firma digitale (art. 12 D.M. 44/2011)."
    )
    return PropostaNote(
        code=CODICE_NOTE_127_TER,
        title=TITOLO_NOTE_127_TER,
        due_date=giorno.isoformat(),
        dies_a_quo=(comunicata_il or decreto.data_pronuncia or giorno).isoformat(),
        norm=NORMA_NOTE_127_TER,
        note=nota,
        ora=ora,
        id_appuntamento=id_appuntamento,
        campi_scadenza={
            "operational_due_at": f"{giorno.isoformat()}T{ora}:00",
            "hearing_mode": MODALITA_NOTE_SCRITTE,
            "hearing_mode_source": fonte or "decreto ex art. 127-ter c.p.c.",
            **({"id_appuntamento": id_appuntamento} if id_appuntamento else {}),
        },
    )


def _testo(oggetto: Any, nome: str) -> str:
    valore = oggetto.get(nome) if isinstance(oggetto, dict) else getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "").strip()


def termine_equivalente(scadenze: Iterable[Any], *, fascicolo_id: str, giorno: date) -> Any | None:
    """Una scadenza del fascicolo che presidia già le note dello stesso giorno.

    Vale la proposta già fatta da un'altra copia del decreto (anche se scartata: l'avvocato ha
    deciso) e ogni termine per note scritte o in sostituzione dell'udienza ancora attivo, anche
    inserito a mano: nessun doppione nello scadenziario.
    """
    if not fascicolo_id:
        return None
    for voce in scadenze or []:
        if _testo(voce, "id_fascicolo") != fascicolo_id or _testo(voce, "data_scadenza")[:10] != giorno.isoformat():
            continue
        codice = _testo(voce, "deadline_profile_code").upper()
        if codice == CODICE_NOTE_127_TER:
            return voce
        if codice == PRESIDIO_OPERATIVO:
            # Il presidio automatico della PEC non è il termine legale (niente perentorietà né orario):
            # non impedisce la bozza, che alla conferma lo assorbe (GestioneScadenziario.conferma_bozza).
            continue
        if _testo(voce, "stato").upper() != "ANNULLATO" and _RE_NOTE_SCRITTE.search(_testo(voce, "titolo")):
            return voce
    return None


__all__ = [
    "CODICE_NOTE_127_TER", "FINE_GIORNO", "MODALITA_NOTE_SCRITTE", "NORMA_NOTE_127_TER",
    "PropostaNote", "TITOLO_NOTE_127_TER", "proposta_note", "termine_equivalente",
]
