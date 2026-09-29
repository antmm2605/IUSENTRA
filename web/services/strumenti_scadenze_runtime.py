"""Dagli strumenti legali allo scadenziario: il termine calcolato diventa una scadenza del fascicolo.

La data non arriva dal browser: il calcolo si rifà sul server con gli stessi dati e si prende la
scadenza proposta scelta (``scadenze_proposte[indice]``). Una scadenza già creata con lo stesso calcolo
non si duplica (marcatore nelle note). Base: art. 172 c.p.p. e norme richiamate da ciascun calcolatore.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Callable, Mapping


def _marcatore(tool: str, dati: Mapping[str, Any], voce: Mapping[str, Any], id_fascicolo: str) -> str:
    impronta = hashlib.sha256(json.dumps(
        {"tool": tool, "dati": {k: str(v) for k, v in sorted(dati.items())}, "voce": dict(voce), "fascicolo": id_fascicolo},
        ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    return f"TERMINE_STRUMENTO:{impronta}"


def crea_scadenza(*, tool: str, dati: Mapping[str, Any], indice: int, id_fascicolo: str, calcola: Callable[[str, Mapping[str, Any]], dict],
                  scadenziario: Any, oggi: date, id_utente: str, collega_agenda: Callable[..., dict]) -> tuple[dict[str, Any], int]:
    from pct.scadenziario import TipoTermine

    risultato = calcola(tool, dati)
    proposte = risultato.get("scadenze_proposte") if isinstance(risultato.get("scadenze_proposte"), list) else []
    if not 0 <= indice < len(proposte):
        return {"ok": False, "errore": "Questo calcolo non propone la scadenza indicata."}, 400
    voce = proposte[indice]
    try:
        scade = date.fromisoformat(str(voce.get("data") or ""))
    except ValueError:
        return {"ok": False, "errore": "Data della scadenza non valida."}, 400
    if scade < oggi:
        return {"ok": False, "expired": True, "errore": "Termine già scaduto: non riportato nello scadenziario."}, 409
    marcatore = _marcatore(tool, dati, voce, id_fascicolo)
    titolo = str(voce.get("titolo") or "Termine")
    descrizione = " ".join([f"Calcolato con lo strumento «{tool}» ({voce.get('norma', '')})."]
                           + [str(n) for n in (risultato.get("notes") or [])[:3]])
    esistente = next((s for s in scadenziario.tutte(solo_aperte=False) if marcatore in str(getattr(s, "note", "") or "")), None)
    if esistente:
        return {"ok": True, "giaPresente": True, "messaggio": "Scadenza già presente nello scadenziario.",
                "id": esistente.id, "href": f"/scadenziario/{esistente.id}"}, 200
    scadenza = scadenziario.nuova(
        titolo=titolo, tipo=TipoTermine.TERMINE_PERENTORIO, data_scadenza=scade.isoformat(), id_fascicolo=id_fascicolo,
        descrizione=descrizione, perentorio=True, id_utente_responsabile=id_utente,
        note=f"{marcatore}\nNorma: {voce.get('norma', '')}", giorni_preavviso=[30, 15, 7, 1, 0],
    )
    agenda = collega_agenda(marker=marcatore, title=titolo, deadline_date=scade.isoformat(), description=descrizione,
                            id_fascicolo=id_fascicolo)
    if agenda.get("agendaId"):
        scadenza = scadenziario.aggiorna(scadenza.id, id_appuntamento=agenda["agendaId"])
    return {"ok": True, "messaggio": f"Scadenza del {scade.strftime('%d/%m/%Y')} aggiunta allo scadenziario.",
            "id": scadenza.id, "href": f"/scadenziario/{scadenza.id}", "agenda": agenda}, 200


__all__ = ["crea_scadenza"]
