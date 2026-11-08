"""Giro delle Notizie utili: interroga solo le fonti scadute, in parallelo e con tempi limitati.

Ogni fonte ha la propria frequenza (`fonti.Fonte.frequenza_minuti`). Una fonte
che non risponde viene registrata con il motivo e ritentata dopo al massimo
un'ora; le altre proseguono. Le notizie nuove di norme, pronunce e prassi sono
poi inoltrate alla revisione degli aggiornamenti legali (`alimentazione`).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, as_completed
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Callable

import requests

from pct import notizie_utili
from pct.notiziario import adattatori
from pct.notiziario.archivio import ArchivioNotiziario
from pct.notiziario.feed import ROME_TZ, leggi_feed
from pct.notiziario.fonti import FONTI, Fonte
from pct.notiziario.rete import ErroreFonte, RequestGet, scarica

logger = logging.getLogger(__name__)

TEMPO_MASSIMO_GIRO = 150  # secondi per l'intero giro
_RIPROVA_DOPO_ERRORE = timedelta(minutes=60)
_LAVORATORI = 6


def _istante(valore: str) -> datetime | None:
    try:
        istante = datetime.fromisoformat(str(valore or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return istante if istante.tzinfo else istante.replace(tzinfo=timezone.utc)


def fonti_scadute(stato: dict[str, dict[str, Any]], adesso: datetime, *, forza: bool = False) -> list[Fonte]:
    scadute: list[Fonte] = []
    for fonte in FONTI:
        precedente = stato.get(fonte.id) or {}
        ultimo = _istante(precedente.get("ultimo_tentativo") or "")
        attesa = timedelta(minutes=fonte.frequenza_minuti)
        if precedente and not precedente.get("ultimo_esito_ok"):
            attesa = min(attesa, _RIPROVA_DOPO_ERRORE)
        if forza or ultimo is None or adesso - ultimo >= attesa:
            scadute.append(fonte)
    return scadute


def raccogli(fonte: Fonte, *, request_get: RequestGet = requests.get) -> list[dict[str, Any]]:
    if fonte.formato == "rss":
        notizie = adattatori.da_feed(fonte, leggi_feed(scarica(fonte.url, fonte.host_ammessi, request_get=request_get)))
    else:
        righe = notizie_utili.raccogli_pagina_istituzionale(fonte.id, request_get=request_get, limit=12)
        notizie = adattatori.da_pagina_istituzionale(fonte, righe)
    if not notizie:
        raise ErroreFonte("La fonte non ha restituito notizie datate e leggibili.")
    return notizie


def _iso(istante: datetime) -> str:
    return istante.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _messaggio(exc: BaseException) -> str:
    if isinstance(exc, ErroreFonte):
        return str(exc)
    return "La fonte non ha restituito un contenuto leggibile."


def esegui_giro(
    archivio: ArchivioNotiziario,
    *,
    request_get: RequestGet = requests.get,
    forza: bool = False,
    adesso: datetime | None = None,
    inoltra: Callable[[ArchivioNotiziario], Any] | None = None,
    tempo_massimo: int = TEMPO_MASSIMO_GIRO,
) -> dict[str, Any]:
    """Aggiorna le fonti scadute; restituisce il riepilogo per il registro delle pianificazioni."""
    adesso = adesso or datetime.now(timezone.utc)
    quando = _iso(adesso)
    scadute = fonti_scadute(archivio.stato_fonti(), adesso, forza=forza)
    esiti: dict[str, dict[str, Any]] = {}
    nuove_totali = 0
    if scadute:
        esecutore = ThreadPoolExecutor(max_workers=min(_LAVORATORI, len(scadute)))
        futuri = {esecutore.submit(raccogli, fonte, request_get=request_get): fonte for fonte in scadute}
        try:
            for futuro in as_completed(futuri, timeout=tempo_massimo):
                fonte = futuri[futuro]
                try:
                    notizie = futuro.result()
                except Exception as exc:  # una fonte giù non ferma le altre
                    logger.info("[notiziario] %s non aggiornata: %s", fonte.id, exc)
                    esiti[fonte.id] = {"ok": False, "messaggio": _messaggio(exc), "voci": 0, "nuove": 0}
                    continue
                nuove = archivio.salva(notizie)
                nuove_totali += len(nuove)
                esiti[fonte.id] = {"ok": True, "messaggio": "", "voci": len(notizie), "nuove": len(nuove)}
        except FuturesTimeout:
            for fonte in scadute:
                esiti.setdefault(fonte.id, {
                    "ok": False, "messaggio": "La fonte non ha risposto entro il tempo massimo del giro.", "voci": 0, "nuove": 0,
                })
        finally:
            esecutore.shutdown(wait=False, cancel_futures=True)
        for fonte_id, esito in esiti.items():
            archivio.registra_esito(fonte_id, ok=esito["ok"], quando=quando, messaggio=esito["messaggio"], voci=esito["voci"])
    archivio.pota(oggi=adesso.astimezone(ROME_TZ).date())
    inoltrate = 0
    if inoltra is not None:
        try:
            inoltrate = int(inoltra(archivio) or 0)
        except Exception as exc:  # la revisione degli aggiornamenti legali non deve fermare il notiziario
            logger.warning("[notiziario] inoltro alla revisione non riuscito: %s", exc)
    return {
        "ok": all(esito["ok"] for esito in esiti.values()) if esiti else True,
        "status": "completato" if esiti else "nessuna_fonte_scaduta",
        "fonti_interrogate": len(esiti),
        "fonti_non_raggiungibili": sorted(fonte_id for fonte_id, esito in esiti.items() if not esito["ok"]),
        "notizie_nuove": nuove_totali,
        "inoltrate_revisione": inoltrate,
        "esiti": esiti,
        "eseguito_il": quando,
    }


__all__ = ["TEMPO_MASSIMO_GIRO", "esegui_giro", "fonti_scadute", "raccogli"]
