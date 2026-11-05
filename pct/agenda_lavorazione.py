"""La lavorazione di un impegno d'agenda: ciò che il software ha preparato e l'avvocato conferma.

Un impegno (udienza, comunicazione di cancelleria, termine, notifica) porta con sé le proposte nate dalla stessa
PEC o dallo stesso provvedimento: termini in bozza da confermare o scartare (artt. 152-155 c.p.c.; nessun termine
diventa operativo senza la conferma dell'avvocato), il collegamento dell'udienza da remoto (art. 127-bis c.p.c.) e
il prossimo passo. Qui solo regole pure sugli oggetti dello scadenziario e dell'agenda: nessuna lettura di file.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

#: riferimenti alla PEC d'origine scritti dalla pipeline nelle note di scadenze e appuntamenti
_RE_PEC = re.compile(r"\b(?:PEC_AUDIT|PEC_TERMINE_PROPOSTO|PEC_RICEZIONE|PEC_TERMINE):(pec_[A-Za-z0-9]+)")
_RE_FASCICOLO = re.compile(r"^Fascicolo:\s*([A-Za-z0-9_-]{4,})\s*$", re.M)
_RE_ATTIVITA = re.compile(r"^Attività per l'avvocato:\s*(.+)$", re.M)
_RE_NOTIFICA = re.compile(r"IUSENTRA_LEGAL_NOTIFICATION:[\w-]+:([0-9a-f-]{8,})")
_BOZZA = "BOZZA"
_MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
         "novembre", "dicembre")


def _campo(oggetto: Any, nome: str) -> Any:
    return oggetto.get(nome) if isinstance(oggetto, Mapping) else getattr(oggetto, nome, None)


def _testo(oggetto: Any, nome: str) -> str:
    valore = _campo(oggetto, nome)
    return str(getattr(valore, "value", valore) or "").strip()


def riferimenti_pec(oggetto: Any) -> set[str]:
    """Le PEC d'origine di un impegno o di una scadenza (note, uid esterno, messaggio di provenienza)."""
    testo = "\n".join(_testo(oggetto, n) for n in ("note", "descrizione", "external_uid", "source_message_id"))
    trovati = set(_RE_PEC.findall(testo))
    diretto = _testo(oggetto, "source_message_id")
    if diretto.startswith("pec_"):
        trovati.add(diretto)
    return trovati


def fascicolo_dell_impegno(oggetto: Any) -> str:
    """Il fascicolo collegato: il campo esplicito, altrimenti la riga «Fascicolo: …» scritta dalla pipeline PEC."""
    esplicito = _testo(oggetto, "id_fascicolo")
    if esplicito:
        return esplicito
    trovato = _RE_FASCICOLO.search(_testo(oggetto, "note"))
    return trovato.group(1) if trovato else ""


def e_bozza(scadenza: Any) -> bool:
    return _testo(scadenza, "stato").upper() == _BOZZA


def proposte_collegate(scadenze: Iterable[Any], impegno: Any, *, id_impegno: str = "") -> list[Any]:
    """Le bozze nate dalla stessa PEC dell'impegno, collegate al suo appuntamento, o l'impegno stesso se è una bozza."""
    pec = riferimenti_pec(impegno)
    proprio = _testo(impegno, "id")
    trovate = []
    for scadenza in scadenze or ():
        if not e_bozza(scadenza):
            continue
        stessa = _testo(scadenza, "id") == proprio and e_bozza(impegno)
        dalla_pec = bool(pec & riferimenti_pec(scadenza))
        dall_udienza = bool(id_impegno) and _testo(scadenza, "id_appuntamento") == id_impegno
        if stessa or dalla_pec or dall_udienza:
            trovate.append(scadenza)
    return sorted(trovate, key=lambda s: _testo(s, "data_scadenza"))


def indice_proposte(scadenze: Iterable[Any]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Bozze aperte per PEC d'origine e per appuntamento (id delle bozze, per non contarle due volte)."""
    per_pec: dict[str, set[str]] = defaultdict(set)
    per_appuntamento: dict[str, set[str]] = defaultdict(set)
    for scadenza in scadenze or ():
        if not e_bozza(scadenza):
            continue
        identificativo = _testo(scadenza, "id")
        for pec in riferimenti_pec(scadenza):
            per_pec[pec].add(identificativo)
        appuntamento = _testo(scadenza, "id_appuntamento")
        if appuntamento:
            per_appuntamento[appuntamento].add(identificativo)
    return per_pec, per_appuntamento


def proposte_aperte(impegno: Any, indice: tuple[dict[str, set[str]], dict[str, set[str]]], *, id_impegno: str = "") -> int:
    """Il numero del sigillo «N proposte» per una voce d'agenda."""
    per_pec, per_appuntamento = indice
    trovate: set[str] = set(per_appuntamento.get(id_impegno, set())) if id_impegno else set()
    for pec in riferimenti_pec(impegno):
        trovate |= per_pec.get(pec, set())
    if e_bozza(impegno):
        trovate.add(_testo(impegno, "id") or "propria")
    return len(trovate)


def data_italiana(valore: str) -> str:
    try:
        giorno = date.fromisoformat(str(valore or "")[:10])
    except ValueError:
        return ""
    return f"{giorno.day} {_MESI[giorno.month - 1]} {giorno.year}"


def _ora(scadenza: Any) -> str:
    operativa = _testo(scadenza, "operational_due_at")
    ora = operativa[11:16] if len(operativa) >= 16 else ""
    return "" if ora in ("", "00:00", "23:59") else ora


def _spiegazione(note: str) -> str:
    """Il calcolo e la regola dalla nota della bozza, senza i marcatori tecnici."""
    righe = []
    for riga in str(note or "").splitlines():
        riga = riga.strip()
        if not riga or re.match(r"^(?:PEC_\w+|IUSENTRA_\w+):", riga) or riga.startswith("Regola "):
            continue
        riga = re.sub(r"^(?:Termine proposto|Calcolo|Nota):\s*", "", riga)
        righe.append(riga)
    return " ".join(righe)[:420]


def voce_proposta(scadenza: Any) -> dict[str, Any]:
    """La proposta come la legge l'avvocato: che cosa, entro quando, perché, con le due azioni."""
    identificativo = _testo(scadenza, "id")
    ora = _ora(scadenza)
    return {
        "id": identificativo,
        "titolo": re.sub(r"\s+[–-]\s+(?:RG|R\.G\.)\s+\S+.*$", "", _testo(scadenza, "titolo")),
        "data": _testo(scadenza, "data_scadenza")[:10],
        "dataEtichetta": data_italiana(_testo(scadenza, "data_scadenza")) + (f" ore {ora}" if ora else ""),
        "perentorio": bool(_campo(scadenza, "perentorio")),
        "spiegazione": _spiegazione(_testo(scadenza, "note")),
        "confermaHref": f"/scadenziario/{identificativo}/conferma-proposta",
        "scartaHref": f"/scadenziario/{identificativo}/scarta-proposta",
    }


def prossimo_passo(*note: str) -> str:
    for testo in note:
        trovato = _RE_ATTIVITA.search(str(testo or ""))
        if trovato:
            passo = trovato.group(1).strip()
            return passo[:1].upper() + passo[1:]
    return ""


def notifica_collegata(*note: str) -> str:
    """L'identificativo della notifica legale presidiata, se l'impegno nasce dal presidio notifiche."""
    for testo in note:
        trovato = _RE_NOTIFICA.search(str(testo or ""))
        if trovato:
            return trovato.group(1)
    return ""


def collegamento_remoto(appuntamento: Any) -> dict[str, str]:
    """Link, ID riunione e codice dell'udienza da remoto (art. 127-bis c.p.c.), se registrati."""
    link = _testo(appuntamento, "remote_hearing_url")
    if not link:
        return {}
    return {
        "link": link,
        "piattaforma": _testo(appuntamento, "remote_hearing_platform"),
        "idRiunione": _testo(appuntamento, "remote_hearing_meeting_id"),
        "codice": _testo(appuntamento, "remote_hearing_passcode"),
        "verificato": "sì" if _campo(appuntamento, "remote_hearing_verified") else "",
    }


__all__ = [
    "collegamento_remoto", "data_italiana", "e_bozza", "fascicolo_dell_impegno", "indice_proposte",
    "notifica_collegata", "proposte_aperte", "proposte_collegate", "prossimo_passo", "riferimenti_pec", "voce_proposta",
]
