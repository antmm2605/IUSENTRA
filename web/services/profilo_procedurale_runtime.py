"""Riconvalida notturna dei profili procedurali (vedi `pct.practice_engine.riconvalida_profili`).

Il giro gira nella corsia lunga dello scheduler, di notte, per ogni studio attivo e a lotti: i
fascicoli senza profilo si ripassano con il resolver corrente; quelli identificati dai dati certi
ricevono il profilo con la fonte nell'audit, gli altri restano proposte da confermare. Un profilo
già salvato (confermato dall'avvocato o impostato in precedenza) non si tocca. L'esito per la
console «Pianificazioni» contiene solo conteggi.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from flask import current_app, g

logger = logging.getLogger(__name__)

JOB_ID = "profili_procedurali_riconvalida"
LOTTO_PREDEFINITO = 300
_SOMME = ("esaminati", "gia_salvati", "impostati", "da_confermare", "errori", "restano")


def lotto_riconvalida(config: Mapping[str, Any] | None = None) -> int:
    grezzo = (config or {}).get("IUSENTRA_PROFILI_RICONVALIDA_LOTTO") or os.getenv("IUSENTRA_PROFILI_RICONVALIDA_LOTTO")
    try:
        return max(1, min(int(grezzo or LOTTO_PREDEFINITO), 5000))
    except (TypeError, ValueError):
        return LOTTO_PREDEFINITO


def riconvalida_profili_studio(*, limite: int = 0) -> dict[str, Any]:
    """Ripassa i fascicoli senza profilo dello studio corrente e invalida la Lettura di quelli impostati."""
    from pct.practice_engine.riconvalida_profili import riconvalida_profili
    from web.services.lettura_cache import invalida_lettura
    from web.services.react_practice_engine_bridge import _etichette_catalogo

    core = current_app.extensions["core_runtime"]
    fascicoli = list(core["get_fascicoli"]().tutti())

    def _etichette(fascicolo_id: str) -> list[str]:
        try:
            return _etichette_catalogo(fascicolo_id)
        except Exception:
            logger.debug("Catalogo non disponibile per il profilo di %s", fascicolo_id, exc_info=True)
            return []

    esito = riconvalida_profili(core["get_practice_engine"](), fascicoli, etichette_di=_etichette, limite=limite)
    for fascicolo_id in esito["fascicoli_impostati"]:
        try:
            invalida_lettura(fascicolo_id)
        except Exception:
            logger.debug("Lettura di %s non invalidata", fascicolo_id, exc_info=True)
    return esito


def _esito_studio(studio: str, *, limite: int) -> dict[str, Any]:
    try:
        esito = riconvalida_profili_studio(limite=limite)
    except Exception as exc:  # uno studio guasto non ferma gli altri, ma rende rosso l'esito
        logger.warning("Riconvalida profili non riuscita per %s: %s", studio, exc)
        esito = {"errori": 1, "errore": type(exc).__name__}
    return {"studio": studio, **{k: v for k, v in esito.items() if k in (*_SOMME, "errore")}}


def riconvalida_profili_notturna(app: Any) -> dict[str, Any]:
    """Un lotto per ogni studio attivo; l'esito è «ok» solo se nessuno studio ha avuto errori."""
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    limite = lotto_riconvalida(app.config)
    studi: list[dict[str, Any]] = []
    attivi = _active_tenants(app)
    if not attivi:
        with app.test_request_context("/__scheduler/profili-procedurali/default"):
            g.multi_tenant_enabled = False
            g.tenant_context_missing = False
            g.tenant_context_slug = ""
            studi.append(_esito_studio("default", limite=limite))
    else:
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for studio in attivi:
            slug = str(getattr(studio, "slug", "") or "").strip().lower()
            if not slug:
                continue
            with app.test_request_context(f"/__scheduler/profili-procedurali/{slug}"):
                try:
                    _attach_tenant_context(manager, studio)
                except Exception as exc:
                    studi.append({"studio": slug, "errori": 1, "errore": type(exc).__name__})
                    continue
                studi.append(_esito_studio(slug, limite=limite))
    totali = {chiave: sum(int(studio.get(chiave) or 0) for studio in studi) for chiave in _SOMME}
    return {"ok": totali["errori"] == 0, "job": JOB_ID, "lotto": limite, "studi": len(studi), "totals": totali, "tenants": studi}


__all__ = ["JOB_ID", "LOTTO_PREDEFINITO", "lotto_riconvalida", "riconvalida_profili_notturna", "riconvalida_profili_studio"]
