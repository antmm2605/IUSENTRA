"""La stessa udienza vista da più fonti resta una sola voce d'agenda.

Una udienza ha un'identità giuridica: il procedimento (fascicolo o numero di ruolo), il giorno
e l'ora (artt. 82 e 168-bis c.p.c.: data e ora fissate dal giudice). PEC di cancelleria, lettura
dei documenti, portale, importazione PDP e calendari esterni possono descriverla ciascuno per
conto proprio: la seconda fonte si aggiunge come prova alla voce esistente invece di crearne
un'altra. Un'ora assente o segnaposto («ora da confermare») è compatibile con qualsiasi ora;
quando arriva l'ora certa, sostituisce il segnaposto.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

ORA_DA_CONFERMARE = "Ora da confermare: la fonte non indica l'orario dell'udienza."
_STATI_CHIUSI = {"ANNULLATO", "COMPLETATO"}


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def _ruolo(valore: str) -> str:
    trovato = re.search(r"(\d{1,7})\s*/\s*(\d{4})", str(valore or ""))
    return f"{int(trovato.group(1))}/{trovato.group(2)}" if trovato else ""


def ora_da_confermare(appuntamento: Any) -> bool:
    return ORA_DA_CONFERMARE in _valore(appuntamento, "note")


def udienza_equivalente(
    appuntamenti: Iterable[Any], *, id_fascicolo: str = "", procedimento: str = "", data_ora: str, ora_certa: bool = True,
) -> Any | None:
    """La voce UDIENZA già in agenda per lo stesso procedimento, giorno e ora compatibile; None se non c'è."""
    giorno, ora = str(data_ora or "")[:10], str(data_ora or "")[11:16]
    ruolo = _ruolo(procedimento)
    if not giorno or (not id_fascicolo and not ruolo):
        return None
    for appuntamento in appuntamenti:
        if _valore(appuntamento, "tipo") != "UDIENZA" or _valore(appuntamento, "stato") in _STATI_CHIUSI:
            continue
        if _valore(appuntamento, "data_ora")[:10] != giorno:
            continue
        stesso_fascicolo = bool(id_fascicolo) and _valore(appuntamento, "id_fascicolo") == id_fascicolo
        stesso_ruolo = bool(ruolo) and _ruolo(_valore(appuntamento, "procedimento")) == ruolo
        if not (stesso_fascicolo or stesso_ruolo):
            continue
        if not ora_certa or ora_da_confermare(appuntamento) or _valore(appuntamento, "data_ora")[11:16] == ora:
            return appuntamento
    return None


def riunisci_fonte(agenda: Any, appuntamento: Any, *, fonte: str, data_ora: str, ora_certa: bool) -> Any:
    """Aggiunge la fonte come prova; l'ora certa sostituisce il segnaposto. Restituisce la voce aggiornata."""
    note = _valore(appuntamento, "note")
    campi: dict[str, Any] = {}
    riga = f"Fonte aggiuntiva: {fonte}"
    if fonte and riga not in note:
        note = f"{note}\n{riga}".strip()
        campi["note"] = note
    if ora_certa and ora_da_confermare(appuntamento) and str(data_ora or "")[:10] == _valore(appuntamento, "data_ora")[:10]:
        campi["data_ora"] = data_ora
        campi["note"] = "\n".join(linea for linea in note.splitlines() if linea.strip() != ORA_DA_CONFERMARE)
    return agenda.modifica(_valore(appuntamento, "id"), **campi) if campi else appuntamento


__all__ = ["ORA_DA_CONFERMARE", "ora_da_confermare", "riunisci_fonte", "udienza_equivalente"]
