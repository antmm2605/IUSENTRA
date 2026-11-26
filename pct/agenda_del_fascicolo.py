"""Quali appuntamenti dell'agenda appartengono a un fascicolo.

L'appuntamento non ha un campo «fascicolo»: il legame passa dal campo ``procedimento`` («RG numero/anno», il numero
di ruolo che identifica la causa presso l'ufficio, art. 168 c.p.c. e art. 36 disp. att. c.p.c.) o, per gli impegni
non giudiziari, dal cliente. Un cliente può avere più cause: un appuntamento che nomina il ruolo di un'altra causa non
appartiene a questo fascicolo anche se il cliente è lo stesso, e un'udienza non si attribuisce mai per il solo cliente.

Collaudo 10/11/2026: l'udienza del 26/02/2026 dell'espropriazione RG 792/2025 compariva nella Lettura del decreto
ingiuntivo RG 4202/2024 dello stesso cliente («Registrare l'esito dell'udienza del 26/02/2026 (art. 183)»).
"""

from __future__ import annotations

import re
from typing import Any
from legal_ocr.formulario.riferimenti_normativi import atto_normativo_prima

_RE_RUOLO = re.compile(r"(\d{1,7})\s*/\s*(\d{4})")


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _ruolo(valore: Any) -> str:
    testo = _testo(valore)
    trovato = next((m for m in _RE_RUOLO.finditer(testo) if not atto_normativo_prima(testo, m.start(1))), None)
    return f"{int(trovato.group(1))}/{trovato.group(2)}" if trovato else ""


def ruoli_dei_fascicoli(fascicoli: Any) -> frozenset[str]:
    """I ruoli («numero/anno») di tutti i fascicoli dello studio."""
    return frozenset(r for f in fascicoli or () if (r := chiavi_fascicolo(f)["ruolo"]))


def chiavi_fascicolo(fascicolo: Any) -> dict[str, Any]:
    """Le chiavi con cui un appuntamento si collega al fascicolo: id, numero interno, ruolo, cliente."""
    numero, anno = _testo(getattr(fascicolo, "numero_rg", "")), _testo(getattr(fascicolo, "anno_rg", ""))
    ruolo = _ruolo(f"{numero}/{anno}") if numero and anno and "/" not in numero else _ruolo(numero) or _ruolo(getattr(fascicolo, "rg_completo", ""))
    testuali = {_testo(getattr(fascicolo, campo, "")).lower() for campo in ("id", "numero", "rg_completo")}
    if numero:
        testuali.add(numero.lower())
    testuali.discard("")
    return {"ruolo": ruolo, "testuali": testuali, "cliente": _testo(getattr(fascicolo, "id_cliente", "")).lower()}


def appuntamento_del_fascicolo(appuntamento: Any, chiavi: dict[str, Any], *, ruoli_dello_studio: set[str] | frozenset[str] = frozenset()) -> bool:
    """True se l'appuntamento appartiene al fascicolo descritto da ``chiavi_fascicolo``.

    1. il procedimento indica un ruolo: vale solo se è il ruolo del fascicolo;
    2. il procedimento coincide con id, numero interno o ruolo scritto per esteso del fascicolo;
    3. senza procedimento, l'impegno del cliente (colloquio, scadenza dello studio) vale per il cliente, ma un'udienza
       senza procedimento non si attribuisce per il solo cliente;
    4. un fascicolo che non ha ancora il ruolo nella scheda prende per cliente l'appuntamento con un ruolo che non è di
       nessun altro fascicolo dello studio (``ruoli_dello_studio``): la causa è iscritta ma la scheda non è aggiornata.
    """
    procedimento = _testo(getattr(appuntamento, "procedimento", ""))
    ruolo = _ruolo(procedimento)
    cliente = _testo(getattr(appuntamento, "id_cliente", "")).lower()
    if ruolo:
        if not chiavi.get("ruolo"):
            return bool(cliente) and cliente == chiavi.get("cliente") and ruolo not in ruoli_dello_studio
        return ruolo == chiavi["ruolo"]
    if procedimento:
        return procedimento.lower() in chiavi.get("testuali", set())
    tipo = _testo(getattr(getattr(appuntamento, "tipo", ""), "value", getattr(appuntamento, "tipo", ""))).upper()
    return bool(cliente) and cliente == chiavi.get("cliente") and tipo != "UDIENZA"


_STATI_ESCLUSI = {"ANNULLATO", "CANCELLATO"}


def udienze_in_agenda(appuntamenti: Any) -> set[str]:
    """I giorni (ISO) delle udienze presenti in agenda e non annullate, fra gli appuntamenti già del fascicolo.

    Un'udienza in agenda è un dato confermato dello studio: la stessa data rilevata da un documento non è più una
    «rilevazione da verificare» (collaudo 10/11/2026, Tribunale di Reggio Calabria, udienza del 16/04/2026).
    """
    giorni: set[str] = set()
    for appuntamento in appuntamenti or ():
        tipo = _testo(getattr(getattr(appuntamento, "tipo", ""), "value", getattr(appuntamento, "tipo", ""))).upper()
        stato = _testo(getattr(getattr(appuntamento, "stato", ""), "value", getattr(appuntamento, "stato", ""))).upper()
        giorno = _testo(getattr(appuntamento, "data_ora", ""))[:10]
        if tipo == "UDIENZA" and stato not in _STATI_ESCLUSI and len(giorno) == 10:
            giorni.add(giorno)
    return giorni


__all__ = ["appuntamento_del_fascicolo", "chiavi_fascicolo", "ruoli_dei_fascicoli", "udienze_in_agenda"]
