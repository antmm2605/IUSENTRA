"""Giro pianificato delle ricevute dei depositi telematici, studio per studio (difetto 27, 09/11/2026).

Il lavoro ``polling_esiti_deposito`` (ogni 15 minuti) leggeva i percorsi generali dell'app: in produzione
multi-studio ``/data/fascicoli/fascicoli.json`` è vuoto e ``/data/email/pec_audit.sqlite`` non è l'archivio di
alcuno studio, quindi le ricevute (D.M. 44/2011 artt. 13-14, Specifiche DGSIA) si aggiornavano solo aprendo il
fascicolo. Ora il giro passa ogni studio attivo con i suoi fascicoli, la sua configurazione PEC e il suo
archivio PEC, con gli stessi strumenti del presidio fascicoli/economia (``fascicoli_presidi_runtime``).

Lo stato di un deposito cambia solo con la ricevuta collegata per Message-ID (``applica_ricevute``): il deposito
si perfeziona con la ricevuta di avvenuta consegna (art. 196-sexies disp. att. c.p.c.). Dell'archivio PEC si
leggono le sole intestazioni delle ricevute (``ricevute_da_archivio``): nessuna lettura dei documenti.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger("pct.scheduler")

JOB_ID = "polling_esiti_deposito"


def _config_pec(percorso: str) -> Any | None:
    """La casella PEC dello studio, solo se l'accesso IMAP è configurato."""
    from pct.config_studio import GestioneConfigStudio

    try:
        config_pec = getattr(GestioneConfigStudio(config_path=percorso).config, "pec", None)
    except Exception as exc:
        logger.debug("[scheduler] Config PEC non disponibile (%s): %s", percorso, exc)
        return None
    if config_pec and (not getattr(config_pec, "imap_host", "") or not getattr(config_pec, "indirizzo", "")):
        return None  # IMAP non configurato
    return config_pec


def _credenziali_pdp(app: Any) -> dict | None:
    """Credenziali PDP (penale) se presenti: il PDP non ha servizi, il deposito resta solo contato."""
    try:
        p12 = app.config.get("PDP_P12_PATH", os.getenv("PDP_P12_PATH", ""))
        p12_pwd = app.config.get("PDP_P12_PASSWORD", os.getenv("PDP_P12_PASSWORD", ""))
        if p12 and os.path.exists(p12):
            return {"p12_path": p12, "p12_password": p12_pwd}
    except Exception:
        pass
    return None


def _esegui(gf: Any, *, config_pec: Any, credenziali_pdp: dict | None, archivio_pec: Path, giorni: int) -> dict:
    from pct.polling_depositi import esegui_polling

    return esegui_polling(
        gf=gf, config_pec=config_pec, credenziali_pdp=credenziali_pdp,
        archivio_pec=archivio_pec, giorni_indietro=giorni,
    )


def _log_studio(studio: str, report: Mapping[str, Any]) -> None:
    logger.info(
        "[scheduler] Polling depositi (%s): %d controllati, %d aggiornati, %d errori",
        studio, int(report.get("controllati") or 0), int(report.get("aggiornati") or 0),
        int(report.get("errori") or 0),
    )


def _studio_unico(app: Any, *, giorni: int, credenziali_pdp: dict | None) -> dict[str, Any]:
    """Installazione con un solo studio: percorsi dell'app, come prima della correzione."""
    from pct.fascicoli import GestioneFascicoli
    from pct.ricevute_deposito_archivio import percorso_archivio_pec

    fascicoli_db = app.config.get("FASCICOLI_DB", "./fascicoli/fascicoli.json")
    if not os.path.exists(fascicoli_db):
        return {"tenant": "default", "esito": "archivio_fascicoli_assente", "controllati": 0, "aggiornati": 0, "errori": 0}
    gf = GestioneFascicoli(
        db_path=fascicoli_db,
        documents_dir=app.config.get("FASCICOLI_DOCS", "./fascicoli/documenti"),
        archive_dir=app.config.get("FASCICOLI_ARCH", "./fascicoli/archivio"),
    )
    config_pec = _config_pec(app.config.get("STUDIO_CONFIG") or app.config.get("CONFIG_STUDIO_DB", "./config/studio.json"))
    report = _esegui(gf, config_pec=config_pec, credenziali_pdp=credenziali_pdp,
                     archivio_pec=percorso_archivio_pec(app.config), giorni=giorni)
    if report.get("controllati"):
        _log_studio("default", report)
    return {"tenant": "default", "esito": "controllate", **report}


def _studio(app: Any, manager: Any, studio: Any, *, giorni: int, credenziali_pdp: dict | None) -> dict[str, Any]:
    """Un giro sui depositi di uno studio, nel suo contesto: fascicoli, casella e archivio PEC suoi."""
    from pct.ricevute_deposito_archivio import percorso_archivio_pec
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context, _text

    slug = _text(getattr(studio, "slug", "")).lower()
    paths = dict(manager.percorsi_dati(slug, reconcile_aliases=False, ensure_baseline=False))
    # Solo i percorsi dello studio: l'archivio generale dell'app (PEC_AUDIT_DB) non è di alcuno studio.
    archivio_pec = percorso_archivio_pec({"EMAIL_CASELLA_DB": paths.get("EMAIL_CASELLA_DB", "")})
    config_pec = _config_pec(_text(paths.get("STUDIO_CONFIG")))
    if config_pec is None and credenziali_pdp is None and not archivio_pec.is_file():
        return {"tenant": slug, "esito": "pec_non_configurata", "controllati": 0, "aggiornati": 0, "errori": 0}
    with app.test_request_context(f"/__scheduler/polling-depositi/{slug}"):
        _attach_tenant_context(manager, studio)
        from web.helpers import get_fascicoli

        report = _esegui(get_fascicoli(), config_pec=config_pec, credenziali_pdp=credenziali_pdp,
                         archivio_pec=archivio_pec, giorni=giorni)
    _log_studio(slug, report)
    return {"tenant": slug, "esito": "controllate", **report}


def run_polling_esiti_deposito(app: Any, *, giorni: int) -> dict[str, Any]:
    """Il lavoro ``polling_esiti_deposito``: ogni studio attivo, oppure l'installazione con un solo studio."""
    from web.services.fascicoli_presidi_runtime import _active_tenants

    credenziali_pdp = _credenziali_pdp(app)
    studi: list[dict[str, Any]] = []
    if app.config.get("MULTI_TENANT"):
        active = _active_tenants(app)
        if not active:
            logger.error("[scheduler] %s non eseguito: nessuno studio attivo o registro studi non leggibile", JOB_ID)
            return {"ok": False, "job": JOB_ID, "error": "nessuno studio attivo: nessun deposito da controllare",
                    "source_of_truth": "registro studi del worker scheduler", "tenants": []}
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for studio in active:
            try:
                studi.append(_studio(app, manager, studio, giorni=giorni, credenziali_pdp=credenziali_pdp))
            except Exception as exc:  # uno studio guasto non ferma gli altri
                slug = str(getattr(studio, "slug", "") or "tenant")
                logger.error("[scheduler] Polling depositi (%s) fallito: %s", slug, exc)
                studi.append({"tenant": slug, "esito": "polling_fallito", "error": str(exc)[:200]})
    else:
        studi.append(_studio_unico(app, giorni=giorni, credenziali_pdp=credenziali_pdp))
    falliti = [voce["tenant"] for voce in studi if voce.get("error")]
    return {
        "ok": not falliti,
        "job": JOB_ID,
        "error": ("polling fallito per: " + ", ".join(falliti)) if falliti else "",
        "source_of_truth": "fascicoli e archivio PEC di ciascuno studio",
        "controllati": sum(int(voce.get("controllati") or 0) for voce in studi),
        "aggiornati": sum(int(voce.get("aggiornati") or 0) for voce in studi),
        "errori": sum(int(voce.get("errori") or 0) for voce in studi),
        "tenants": studi,
    }


__all__ = ["run_polling_esiti_deposito"]
