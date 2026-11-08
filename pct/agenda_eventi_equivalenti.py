"""La stessa udienza vista da più fonti resta una sola voce d'agenda.

Una udienza ha un'identità giuridica: il procedimento (fascicolo o numero di ruolo), il giorno
e l'ora (artt. 82 e 168-bis c.p.c.: data e ora fissate dal giudice). PEC di cancelleria, lettura
dei documenti, portale, importazione PDP e calendari esterni possono descriverla ciascuno per
conto proprio: la seconda fonte si aggiunge come prova alla voce esistente invece di crearne
un'altra. Un'ora assente o segnaposto («ora da confermare») è compatibile con qualsiasi ora;
quando arriva l'ora certa, sostituisce il segnaposto.

Trattazione scritta: «Il giorno di scadenza del termine assegnato per il deposito delle note di cui al presente
articolo è considerato data di udienza a tutti gli effetti» (art. 127-ter c.p.c., testo vigente, Normattiva,
verificato l'08/11/2026). La voce SCADENZA «Deposito note scritte ex art. 127-ter» e l'UDIENZA dello stesso
procedimento, giorno e ora sono quindi lo stesso evento (caso reale RG 901/2026: voci 35B49E1F e 35D9908A del
06/10/2026 ore 14:00). Gli altri termini dell'articolo (opposizione entro cinque giorni) restano distinti.
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


_NOTE_127_TER = re.compile(r"\bnote\b.*(127\s*-?\s*ter|sostituzione\s+(dell['’]\s*)?udienza|trattazione\s+scritta)", re.I)


def titolo_note_127_ter(titolo: str) -> bool:
    """Titolo del termine per il deposito delle note scritte (non dell'opposizione alla trattazione scritta)."""
    testo = str(titolo or "")
    return bool(_NOTE_127_TER.search(testo)) and "opposizion" not in testo.lower()


def termine_note_127_ter(appuntamento: Any) -> bool:
    """Voce SCADENZA del deposito delle note scritte: vale come udienza (art. 127-ter c.p.c.)."""
    return _valore(appuntamento, "tipo") == "SCADENZA" and titolo_note_127_ter(_valore(appuntamento, "titolo"))


def evento_udienza(appuntamento: Any) -> bool:
    """UDIENZA o termine per le note 127-ter: la stessa identità di udienza per le regole di equivalenza."""
    return _valore(appuntamento, "tipo") == "UDIENZA" or termine_note_127_ter(appuntamento)


def udienza_equivalente(
    appuntamenti: Iterable[Any], *, id_fascicolo: str = "", procedimento: str = "", data_ora: str, ora_certa: bool = True,
) -> Any | None:
    """La voce UDIENZA (o termine note 127-ter) già in agenda per lo stesso procedimento, giorno e ora; None se non c'è."""
    giorno, ora = str(data_ora or "")[:10], str(data_ora or "")[11:16]
    ruolo = _ruolo(procedimento)
    if not giorno or (not id_fascicolo and not ruolo):
        return None
    for appuntamento in appuntamenti:
        if not evento_udienza(appuntamento) or _valore(appuntamento, "stato") in _STATI_CHIUSI:
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


__all__ = ["ORA_DA_CONFERMARE", "evento_udienza", "ora_da_confermare", "riunisci_fonte", "termine_note_127_ter", "titolo_note_127_ter", "udienza_equivalente"]
