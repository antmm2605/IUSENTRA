"""Runtime del flusso PEC → documenti del fascicolo per lo scheduler e per la verifica sul server.

Il recupero storico gira nella corsia lunga dello scheduler, di notte, a lotti limitati per studio; l'esito
per la console «Pianificazioni» contiene solo conteggi (``ok``, salvati, .eml, scarti per motivo, errori,
quanti restano). Nessun dato del cliente esce da qui.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Mapping

from pct.pec_fascicolo_documenti import recupera_storico, stato_flusso
from web.services.pec_pipeline_runtime import repository_from_paths

LIMITE_PREDEFINITO = 100
_SOMME = ("esaminati", "completati", "in_attesa_conferma", "salvati", "eml_salvati", "gia_presenti", "scartati", "errori", "restano")


def limite_recupero(config: Mapping[str, Any] | None = None) -> int:
    grezzo = (config or {}).get("IUSENTRA_PEC_FASCICOLO_RECUPERO_LIMITE") or os.getenv("IUSENTRA_PEC_FASCICOLO_RECUPERO_LIMITE")
    try:
        return max(1, min(int(grezzo or LIMITE_PREDEFINITO), 1000))
    except (TypeError, ValueError):
        return LIMITE_PREDEFINITO


def recupero_per_studi(targets: Iterable[tuple[str, Mapping[str, Any]]], *, limite: int) -> dict[str, Any]:
    """Un lotto del recupero per ogni studio; l'esito è «ok» solo se nessuno studio ha avuto errori."""
    totali = dict.fromkeys(_SOMME, 0)
    studi: list[dict[str, Any]] = []
    for etichetta, paths in targets:
        try:
            esito = recupera_storico(repository_from_paths(paths, tenant_label=etichetta), limite=limite)
        except Exception as exc:  # uno studio guasto non ferma gli altri, ma rende rosso l'esito
            esito = {"ok": False, "errori": 1, "errore": type(exc).__name__}
        for chiave in _SOMME:
            totali[chiave] += int(esito.get(chiave) or 0)
        studi.append({"studio": etichetta, **{k: v for k, v in esito.items() if k in (*_SOMME, "ok", "errore")}})
    return {"ok": totali["errori"] == 0, "job": "pec_fascicolo_documenti_recupero", "limite": limite,
            "studi": len(studi), "totals": totali, "tenants": studi}


def studi_attivi(config: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Gli studi su cui gira il presidio (stessa regola dello scheduler), senza creare cartelle."""
    if config.get("MULTI_TENANT"):
        from pct.tenant import GestioneTenant, StatoTenant

        registro = GestioneTenant(registry_path=config["TENANTS_REGISTRY"])
        return [(str(studio.slug or "tenant"), dict(registro.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)))
                for studio in registro.lista() if studio.stato != StatoTenant.SOSPESO]
    chiavi = ("EMAIL_CASELLA_DB", "FASCICOLI_DB", "FASCICOLI_DOCS", "AGENDA_DB", "SCADENZIARIO_DB")
    return [("default", {chiave: config.get(chiave) for chiave in chiavi if config.get(chiave)})]


def stato_per_studi(targets: Iterable[tuple[str, Mapping[str, Any]]]) -> list[dict[str, Any]]:
    """Lo stato verificabile del flusso per ogni studio (solo conteggi)."""
    out = []
    for etichetta, paths in targets:
        try:
            out.append({"studio": etichetta, **stato_flusso(repository_from_paths(paths, tenant_label=etichetta))})
        except Exception as exc:
            out.append({"studio": etichetta, "errore": type(exc).__name__})
    return out


__all__ = ["LIMITE_PREDEFINITO", "limite_recupero", "recupero_per_studi", "stato_per_studi", "studi_attivi"]
