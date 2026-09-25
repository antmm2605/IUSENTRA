"""Capienza della casella PEC dello studio, misurata e segnalata.

Base: art. 20 D.M. 44/2011 (casella con spazio adeguato e avviso di
saturazione); art. 16 co. 6 D.L. 179/2012 (con la casella piena la notifica
al difensore si perfeziona con il deposito in cancelleria e sul PST resta
solo l'avviso «Proc. Penali – Avvisi degli atti depositati in cancelleria»).
La misura è in memoria per 30 minuti per studio; oltre l'80% nasce una
notifica, una al giorno per livello.
"""

from __future__ import annotations

import threading
import time
from datetime import date
from typing import Any

from flask import current_app, g

from pct.pec_capienza import leggi_capienza

DURATA_MEMORIA = 30 * 60
_MEMORIA: dict[str, tuple[float, dict[str, Any]]] = {}
_LOCK = threading.Lock()
LINK_AVVISI = "https://servizipst.giustizia.it/PST/AvvisiPenale"


def _studio() -> str:
    return str(g.get("tenant_slug", "") or g.get("auth_tenant_slug", "") or "default")


def _credenziali() -> tuple[str, int, str, str, bool] | None:
    from web.services.mailbox_sync_runtime import _get_config_pec, mailbox_context_for_current_request

    pec = _get_config_pec(mailbox_context_for_current_request())
    if not pec or not getattr(pec, "imap_host", "") or not getattr(pec, "indirizzo", ""):
        return None
    return (pec.imap_host, int(getattr(pec, "imap_port", 993) or 993), pec.indirizzo, pec.password, bool(getattr(pec, "use_ssl", True)))


def _notifica(esito: dict[str, Any]) -> None:
    try:
        from web.services.notifications_runtime import build_notification_service, current_tenant_id, current_user_id

        critico = esito["livello"] == "critico"
        build_notification_service().create_notification(
            tenant_id=current_tenant_id(), user_id=current_user_id(), type="pec_capienza",
            priority="urgent" if critico else "important",
            title=f"Casella PEC piena al {esito['percentuale']:.0f}%",
            body=("Con la casella piena le notifiche penali si perfezionano con il deposito in cancelleria "
                  "senza arrivarti: libera spazio e controlla gli avvisi sul PST."),
            href=LINK_AVVISI, source_type="pec_capienza", source_id=_studio(),
            dedupe_key=f"PEC_CAPIENZA:{_studio()}:{esito['livello']}:{date.today().isoformat()}",
        )
    except Exception:
        current_app.logger.warning("Notifica capienza PEC non creata", exc_info=True)


def stato_casella(*, forza: bool = False) -> dict[str, Any]:
    chiave = _studio()
    with _LOCK:
        in_memoria = _MEMORIA.get(chiave)
    if in_memoria and not forza and time.monotonic() - in_memoria[0] < DURATA_MEMORIA:
        return in_memoria[1]
    credenziali = _credenziali()
    if credenziali is None:
        esito: dict[str, Any] = {"configurata": False, "supportata": False,
                                 "messaggio": "Casella PEC non configurata: impostala in Impostazioni → Email."}
    else:
        host, porta, utente, password, ssl = credenziali
        try:
            esito = {"configurata": True, **leggi_capienza(host, porta, utente, password, ssl=ssl, timeout=8)}
        except Exception:
            esito = {"configurata": True, "supportata": False, "messaggio": "casella non raggiungibile in questo momento"}
        if esito.get("supportata") and esito.get("livello") in {"attenzione", "critico"}:
            _notifica(esito)
    esito["avvisiPst"] = LINK_AVVISI
    with _LOCK:
        _MEMORIA[chiave] = (time.monotonic(), esito)
    return esito


__all__ = ["stato_casella"]
