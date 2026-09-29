"""Contesto del timer della top bar: nomi di fascicolo e cliente, ore di oggi, ricerca dei collegamenti.

Il timer registra il tempo dedicato alla pratica; alla chiusura diventa una voce del timesheet,
base per i compensi a tempo (art. 13 L. 247/2012; D.M. 55/2014 art. 4) e per la parcella.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import quote

from web.helpers import get_clienti, get_fascicoli, get_timesheet

MASSIMO_RISULTATI = 8


def _testo(valore: Any) -> str:
    return str(valore or "").strip()


def etichetta_fascicolo(fascicolo: Any) -> str:
    if fascicolo is None:
        return ""
    rg = _testo(getattr(fascicolo, "numero_rg", ""))
    numero = _testo(getattr(fascicolo, "numero", ""))
    titolo = _testo(getattr(fascicolo, "titolo", ""))
    riferimento = f"R.G. {rg}" if rg else numero
    return " — ".join(p for p in (riferimento, titolo) if p)


def nome_cliente(cliente: Any) -> str:
    return _testo(getattr(cliente, "nome_completo", "")) if cliente is not None else ""


def collegamenti(case_id: str, client_id: str) -> dict[str, Any]:
    """Nomi leggibili del fascicolo e del cliente collegati a un timer o a una voce."""

    fascicolo = get_fascicoli().get(case_id) if case_id else None
    if fascicolo is not None and not client_id:
        client_id = _testo(getattr(fascicolo, "id_cliente", ""))
    cliente = get_clienti().get(client_id) if client_id else None
    return {
        "caseLabel": etichetta_fascicolo(fascicolo) or None,
        "caseHref": f"/fascicoli/{quote(case_id)}" if fascicolo is not None else None,
        "clientLabel": nome_cliente(cliente) or _testo(getattr(fascicolo, "nome_cliente", "")) or None,
    }


def _mie_voci(user_id: str, username: str) -> list[Any]:
    voci = get_timesheet().per_utente(id_utente=user_id) if user_id else []
    return voci or (get_timesheet().per_utente(username=username) if username else [])


def riepilogo_oggi(user_id: str, username: str, oggi: date) -> dict[str, Any]:
    """Minuti già registrati oggi dall'utente, con le ultime voci."""

    giorno = oggi.isoformat()
    voci = [v for v in _mie_voci(user_id, username) if _testo(v.data_attivita)[:10] == giorno]
    voci.sort(key=lambda v: _testo(v.creato_il), reverse=True)
    ultime = []
    for voce in voci[:4]:
        info = collegamenti(voce.id_fascicolo, voce.id_cliente)
        ultime.append({"descrizione": voce.descrizione, "minuti": int(voce.minuti or 0),
                       "fascicolo": info["caseLabel"], "cliente": info["clientLabel"]})
    return {"minuti": sum(int(v.minuti or 0) for v in voci), "voci": len(voci), "ultime": ultime,
            "href": "/timesheet"}


def recenti(user_id: str, username: str) -> list[dict[str, Any]]:
    """Ultimi fascicoli su cui l'utente ha registrato tempo: un clic per riavviare."""

    visti: list[dict[str, Any]] = []
    voci = sorted(_mie_voci(user_id, username), key=lambda v: _testo(v.creato_il), reverse=True)
    for voce in voci:
        if not voce.id_fascicolo or any(r["caseId"] == voce.id_fascicolo for r in visti):
            continue
        info = collegamenti(voce.id_fascicolo, voce.id_cliente)
        if info["caseLabel"]:
            visti.append({"caseId": voce.id_fascicolo, "clientId": voce.id_cliente or None,
                          "label": info["caseLabel"], "detail": info["clientLabel"] or ""})
        if len(visti) >= 4:
            break
    return visti


def cerca(testo: str) -> list[dict[str, Any]]:
    """Fascicoli e clienti che corrispondono al testo digitato (numero, R.G., titolo, nome)."""

    richiesta = _testo(testo)
    if len(richiesta) < 2:
        return []
    risultati: list[dict[str, Any]] = []
    for fascicolo in get_fascicoli().cerca(testo=richiesta)[:MASSIMO_RISULTATI]:
        risultati.append({"kind": "case", "caseId": fascicolo.id, "clientId": _testo(fascicolo.id_cliente) or None,
                          "label": etichetta_fascicolo(fascicolo),
                          "detail": _testo(getattr(fascicolo, "nome_cliente", ""))})
    for cliente in get_clienti().cerca(testo=richiesta)[: max(2, MASSIMO_RISULTATI - len(risultati))]:
        risultati.append({"kind": "client", "caseId": None, "clientId": cliente.id,
                          "label": nome_cliente(cliente), "detail": "Cliente"})
    return risultati


def per_identificativo(case_id: str, client_id: str) -> list[dict[str, Any]]:
    """Il fascicolo o il cliente aperto nella pagina, con il nome da mostrare nel timer."""

    info = collegamenti(_testo(case_id), _testo(client_id))
    if case_id and info["caseLabel"]:
        fascicolo = get_fascicoli().get(case_id)
        return [{"kind": "case", "caseId": case_id, "clientId": _testo(getattr(fascicolo, "id_cliente", "")) or None,
                 "label": info["caseLabel"], "detail": info["clientLabel"] or ""}]
    if client_id and info["clientLabel"]:
        return [{"kind": "client", "caseId": None, "clientId": client_id, "label": info["clientLabel"], "detail": "Cliente"}]
    return []


def minuti_da_secondi(secondi: int) -> int:
    return max(1, -(-int(secondi or 0) // 60))
