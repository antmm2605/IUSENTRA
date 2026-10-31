"""Esito delle udienze passate registrato dalle fonti certe del fascicolo (V28).

Richiesta dell'avvocato del 31/10/2026: l'esito di un'udienza non va chiesto a mano se
il software lo ha già letto. Dopo un'udienza la cancelleria comunica con PEC il rinvio,
la fissazione di una nuova udienza o di un termine per note, il deposito del
provvedimento o la sentenza (art. 136 c.p.c.; art. 16, c. 4, D.L. 179/2012): sono
eventi già letti dall'archivio (``pct.archivio_letture.presidi.eventi_letti``) con il
giorno della ricevuta certificata.

Regola: il primo evento di cancelleria con data uguale o successiva all'udienza ne dice
l'esito. L'udienza si chiude con la nota della fonte (l'avvocato può riaprirla); senza
un evento resta «esito da registrare». Un evento letto da un documento qualsiasi o non
verificato non basta.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable

MARCATORE = "ESITO_UDIENZA_DA_FONTE"

_DECISIONE = {"sentenza"}
_RINVIO = {"rinvio", "fissazione_udienza", "fissazione_note", "riassegnazione_note"}
_PROVVEDIMENTO = {"deposito_provvedimento", "ordinanza", "decreto"}


def _giorno(valore: Any) -> date | None:
    try:
        return date.fromisoformat(str(valore or "")[:10])
    except ValueError:
        return None


def esito_dalle_fonti(
    giorno_udienza: date,
    eventi: Iterable[dict[str, Any]],
    udienze_successive: Iterable[date] = (),
) -> dict[str, str] | None:
    """Esito ricavato dal primo evento di cancelleria dal giorno dell'udienza in poi."""
    candidati = []
    for evento in eventi:
        giorno = _giorno(evento.get("data_iso"))
        campo = str(evento.get("campo") or "")
        if giorno is None or giorno < giorno_udienza:
            continue
        if campo in _DECISIONE | _RINVIO | _PROVVEDIMENTO:
            # A parità di giorno la sentenza prevale sul provvedimento e questo sul rinvio.
            peso = 0 if campo in _DECISIONE else 1 if campo in _PROVVEDIMENTO else 2
            candidati.append((giorno, peso, campo, evento))
    if not candidati:
        return None
    giorno, _peso, campo, evento = min(candidati, key=lambda c: (c[0], c[1]))
    quando = giorno.strftime("%d/%m/%Y")
    if campo in _DECISIONE:
        esito, testo = "decisa", f"Udienza seguita da sentenza comunicata dalla cancelleria il {quando}."
    elif campo in _PROVVEDIMENTO:
        esito, testo = "provvedimento", f"Udienza seguita da provvedimento comunicato dalla cancelleria il {quando}."
    else:
        nuova = min((g for g in udienze_successive if g > giorno_udienza), default=None)
        esito = "rinviata"
        testo = f"Udienza rinviata (comunicazione di cancelleria del {quando})" + (
            f": nuova udienza il {nuova.strftime('%d/%m/%Y')}." if nuova else "."
        )
    return {"esito": esito, "testo": testo, "fonte": str(evento.get("oggetto_id") or ""), "data_fonte": giorno.isoformat()}


def registra_esiti(
    scadenziario: Any,
    *,
    fascicolo_id: str,
    eventi: list[dict[str, Any]],
    oggi: date,
) -> int:
    """Chiude con la nota della fonte le udienze passate del fascicolo il cui esito è certo."""
    from pct.scadenze_stato import esito_udienza_da_registrare

    voci = list(scadenziario.tutte(solo_aperte=False, id_fascicolo=fascicolo_id))
    udienze = [_giorno(getattr(v, "data_scadenza", "")) for v in voci if str(getattr(getattr(v, "tipo", ""), "value", getattr(v, "tipo", ""))).upper() == "UDIENZA"]
    udienze = [g for g in udienze if g]
    registrate = 0
    for voce in voci:
        if not esito_udienza_da_registrare(voce, oggi) or MARCATORE in str(getattr(voce, "note", "") or ""):
            continue
        giorno = _giorno(getattr(voce, "data_scadenza", ""))
        if giorno is None:
            continue
        esito = esito_dalle_fonti(giorno, eventi, udienze)
        if esito is None:
            continue
        scadenziario.completa(
            getattr(voce, "id"),
            note=f"{MARCATORE}:{esito['esito']}:{esito['data_fonte']}:{esito['fonte']}\n{esito['testo']}",
        )
        registrate += 1
    return registrate


__all__ = ["MARCATORE", "esito_dalle_fonti", "registra_esiti"]
