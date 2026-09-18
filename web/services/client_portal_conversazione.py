"""La conversazione del portale, viva da entrambi i lati.

La chat fra studio e cliente si aggiornava solo ricaricando la pagina: chi
scriveva non sapeva se l'altro avesse letto, e la risposta arrivava quando
capitava. Qui c'e' il pezzo che la tiene viva — un'interrogazione leggera che
chiede **solo i messaggi nuovi**, non l'intera conversazione — usata dalla
pagina dello studio e da quella del cliente.

Perche' non un canale aperto (SSE): il portale del cliente si autentica con un
token e non con la sessione dello studio, e ogni visitatore terrebbe occupato
un worker per tutto il tempo in cui la pagina resta aperta. Una richiesta breve
ogni pochi secondi, solo a scheda visibile, costa meno e sopravvive a proxy,
riconnessioni e telefoni che si addormentano.

Il segnalibro e' il `created_at` dell'ultimo messaggio gia' mostrato: chi
chiede riceve la coda e il nuovo segnalibro. La coda **comprende** l'ultimo
secondo gia' visto, perche' gli orari si salvano al secondo e due messaggi
simultanei non sarebbero distinguibili: chi legge scarta per identificativo
quelli che ha gia'. Ripetere e' recuperabile, perdere un messaggio no.
"""

from __future__ import annotations

import re
from typing import Any

#: «2026-09-18T16:08:39 00:00» — il «+» dell'offset letto come spazio.
_OFFSET_SENZA_PIU = re.compile(r"(\d{2}:\d{2}:\d{2}) (\d{2}:\d{2})$")


def _testo(valore: Any) -> str:
    return str(valore if valore is not None else "").strip()


def _segnalibro(valore: Any) -> str:
    """Il segnalibro ripulito dalla traduzione del «+» in spazio.

    L'orario ISO porta l'offset con il segno piu'; dentro una stringa di
    richiesta quel «+» vale spazio, e il segnalibro tornerebbe indietro di
    un'ora facendo ricomparire messaggi gia' visti. Si rimette il segno invece
    di pretendere che ogni chiamante ricordi di codificarlo.
    """
    testo = _testo(valore)
    return _OFFSET_SENZA_PIU.sub(r"\1+\2", testo)


def _risposta(messaggi: list[dict[str, Any]], *, segnalibro: str, riga: Any) -> dict[str, Any]:
    righe = [riga(messaggio) for messaggio in messaggi]
    ultimo = _testo(messaggi[-1].get("created_at")) if messaggi else segnalibro
    return {
        "ok": True,
        "messages": righe,
        "cursor": ultimo,
        "nuovi": len(righe),
    }


def conversazione_studio(payload: dict[str, Any]) -> dict[str, Any]:
    """I messaggi nuovi di una pratica, per la pagina dello studio."""
    from web.services.react_client_portal_bridge import (
        _can,
        _current_tenant_id,
        _public_row,
        repository_for_current_request,
    )

    if not _can("clienti.leggi") and not _can("messaggi.leggi"):
        return {"ok": False, "code": "forbidden", "message": "Permesso clienti.leggi richiesto."}
    matter_id = _testo(payload.get("matterId"))
    if not matter_id:
        return {"ok": False, "code": "validation_error", "message": "Pratica portale non indicata."}
    repo = repository_for_current_request()
    tenant_id = _current_tenant_id()
    if not repo.get_matter(tenant_id, matter_id):
        return {"ok": False, "code": "validation_error", "message": "Pratica portale non trovata."}
    messaggi = repo.messages_after(tenant_id, matter_id=matter_id, after=_segnalibro(payload.get("since")))
    return _risposta(
        messaggi,
        segnalibro=_segnalibro(payload.get("since")),
        riga=lambda riga: _public_row(riga, include_private=True),
    )


def conversazione_cliente(payload: dict[str, Any]) -> dict[str, Any]:
    """I messaggi nuovi della propria pratica, per la pagina del cliente."""
    from web.services.react_client_portal_bridge import (
        ClientPortalError,
        _current_client_token,
        _invalid_invite_payload,
        _invite_and_repo,
        _public_row,
    )

    try:
        invito, repo = _invite_and_repo(_current_client_token())
    except ClientPortalError:
        return _invalid_invite_payload()
    messaggi = repo.messages_after(
        _testo(invito.get("tenant_id")),
        matter_id=_testo(invito.get("matter_id")),
        after=_segnalibro(payload.get("since")),
    )
    return _risposta(messaggi, segnalibro=_segnalibro(payload.get("since")), riga=_public_row)


__all__ = ["conversazione_cliente", "conversazione_studio"]
