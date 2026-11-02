"""Lo storico delle sentenze già lette, riesaminato a lotti con la regola corrente delle proposte.

Il lettore «proposta_definizione» lavora solo sui testi già salvati (nessuna
decifratura, nessun OCR): non condivide il tetto delle riletture pesanti
notturne. A ogni giro della coda delle letture esamina fino a `LOTTO_PROPOSTE`
fascicoli non ancora esaminati con la versione corrente, i mai esaminati per
primi, entro un budget di tempo. È idempotente: il registro (`superati()` e la
riga del lettore) dice cosa resta, e un fascicolo completo non si riprende.
Un fascicolo rimasto parziale (testi non ancora disponibili) si riprende solo
dopo `ORE_ATTESA_PARZIALI` ore, per non ripeterlo a ogni giro.
Base: art. 132 c.p.c.; art. 88 c.p.a.; artt. 91 e 93 c.p.c. (pct/sentenza_automatica.py).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

LETTORE = "proposta_definizione"
LOTTO_PROPOSTE = 50
BUDGET_SECONDI = 20.0
ORE_ATTESA_PARZIALI = 6


def _testo(valore: Any) -> str:
    return str(valore or "").strip()


def fascicoli_da_esaminare(registro: Any, tenant_id: str, *, limite: int, adesso: datetime | None = None) -> list[str]:
    """Fascicoli letti dai motori e non ancora esaminati con la regola corrente: i mai esaminati, poi i più vecchi."""
    from pct.fascicolo_sentenza_archiviazione import VERSIONE_PROPOSTA
    from web.services.archivio_letture_runtime import LETTORE_DOCUMENTI

    # Il registro scrive in UTC (`…Z`): stessa base per il confronto.
    soglia = ((adesso or datetime.now(timezone.utc)) - timedelta(hours=ORE_ATTESA_PARZIALI)).isoformat()
    proposte = {_testo(r.get("fascicolo_id")): r for r in registro.righe_fascicoli(tenant_id, lettore=LETTORE)}
    candidati = []
    for riga in registro.righe_fascicoli(tenant_id, lettore=LETTORE_DOCUMENTI):
        fascicolo_id = _testo(riga.get("fascicolo_id"))
        esame = proposte.get(fascicolo_id) or {}
        corrente = _testo(esame.get("versione_lettore")) == VERSIONE_PROPOSTA
        if not fascicolo_id or (corrente and _testo(esame.get("stato")) == "completa"):
            continue
        ultimo = _testo(esame.get("aggiornato_il"))
        if corrente and ultimo and ultimo[:19] > soglia[:19]:
            continue  # parziale esaminato da poco: attende i testi
        candidati.append((ultimo, _testo(riga.get("aggiornato_il")), fascicolo_id))
    return [fascicolo_id for *_, fascicolo_id in sorted(candidati)[:max(0, limite)]]


def esamina_proposte_storico(registro: Any, tenant_id: str, carica_fascicolo: Callable[[str], Any], *,
                             limite: int = LOTTO_PROPOSTE, budget_secondi: float = BUDGET_SECONDI) -> dict[str, int]:
    """Un lotto: controllo economico dai fatti già registrati, poi proposte e registrazioni automatiche."""
    from web.services.sentenza_proposte_runtime import aggiorna_proposte_definizione

    report = {"fascicoli": 0, "automatiche": 0, "proposte": 0, "errori": 0}
    inizio = time.monotonic()
    for fascicolo_id in fascicoli_da_esaminare(registro, tenant_id, limite=limite):
        if time.monotonic() - inizio > budget_secondi:
            break
        try:
            fascicolo = carica_fascicolo(fascicolo_id)
            if fascicolo is None:
                registro.segna_fascicolo(tenant_id, fascicolo_id, LETTORE, impronta="", oggetti_totali=0, oggetti_letti=0,
                                         stato="completa", versione=_versione())
                continue
            _controllo_economico(fascicolo_id)
            esito = aggiorna_proposte_definizione(fascicolo, registro, tenant_id)
            report["fascicoli"] += 1
            report["automatiche"] += int(esito.get("automatiche") or 0)
            report["proposte"] += int(esito.get("proposte") or 0)
        except Exception as exc:
            report["errori"] += 1
            logger.warning("Storico delle proposte dalla sentenza non esaminato per %s: %s", fascicolo_id, exc)
    return report


def _versione() -> str:
    from pct.fascicolo_sentenza_archiviazione import VERSIONE_PROPOSTA

    return VERSIONE_PROPOSTA


def _controllo_economico(fascicolo_id: str) -> None:
    """Gli eventi economici nascono dai fatti già registrati: servono alla registrazione automatica."""
    try:
        from web.services.sentenza_economic_runtime import ensure_fascicolo_sentenza_economic_analysis

        ensure_fascicolo_sentenza_economic_analysis(fascicolo_id)
    except Exception as exc:
        logger.debug("Controllo economico non aggiornato per %s: %s", fascicolo_id, exc)


@contextmanager
def _contesto_studio(app: Any, paths: dict[str, Any], tenant_slug: str) -> Iterator[None]:
    """Lo stesso contesto di studio della lettura in sfondo (archivio_letture_runtime.avvia_lettura_in_background)."""
    from flask import g

    with app.test_request_context("/__archivio-letture/proposte-storico"):
        g.data_paths = dict(paths or {})
        g.tenant = None
        g.tenant_context_slug = tenant_slug
        g.tenant_context_required = False
        g.tenant_context_missing = False
        g.storage_runtime = None
        if tenant_slug and app.config.get("MULTI_TENANT"):
            try:
                from pct.tenant import GestioneTenant

                g.tenant = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]).get(tenant_slug)
            except Exception:
                g.tenant = None
        yield


def esamina_proposte_storico_studio(app: Any, registro: Any, tenant_id: str, paths: dict[str, Any]) -> dict[str, int]:
    """Il lotto nel contesto dello studio (dati e tenant come la lettura in sfondo)."""
    try:
        with _contesto_studio(app, paths, tenant_id):
            from web.helpers import get_fascicoli
            from web.services.registro_letture_runtime import tenant_corrente

            # Lo stesso tenant del registro con cui scrive la lettura in sfondo.
            tenant = tenant_corrente() or tenant_id
            return esamina_proposte_storico(registro, tenant, lambda fid: get_fascicoli().get(fid))
    except Exception:
        logger.exception("Lotto delle proposte dalla sentenza non eseguito per %s", tenant_id or "studio")
        return {"fascicoli": 0, "automatiche": 0, "proposte": 0, "errori": 1}


__all__ = ["LOTTO_PROPOSTE", "esamina_proposte_storico", "esamina_proposte_storico_studio", "fascicoli_da_esaminare"]
