"""Addestramento e misura del classificatore piccolo del catalogo, per studio, fuori dalle richieste web.

Legge ciò che è già nel catalogo SQL: proposte delle regole, decisioni dell'avvocato e testo già estratto della
versione catalogata. Nessun documento viene aperto, decifrato o riletto; i testi cifrati della busta restano
fuori. Il riepilogo porta solo conteggi e voci pubblicabili; i disaccordi restano nella cartella dello studio
sul server (`intelligence/classificatore_disaccordi.json`), base della revisione rapida dell'avvocato.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from flask import Flask, g

from pct.document_intelligence.verita import etichette_dalle_decisioni
from pct.document_intelligence.verita.classificatore import CARATTERI_LETTI
from pct.document_intelligence.verita.esperimento import Campione, misura
from web.services.verita_catalogo_runtime import conferme_massive

logger = logging.getLogger(__name__)

FILE_DISACCORDI = "classificatore_disaccordi.json"


def _testo(repository, tenant_id: str, assegnazione) -> str:
    document_ai_id = str(getattr(assegnazione, "document_ai_id", "") or "")
    versione = str(getattr(assegnazione, "document_version_id", "") or "")
    if not document_ai_id or not versione:
        return ""
    estratto = repository.get_extracted_text(tenant_id, str(assegnazione.fascicolo_id), document_ai_id, versione)
    testo = str(getattr(estratto, "text", "") or "")
    return "" if testo.lstrip().startswith("PCTENC") else testo[:CARATTERI_LETTI]


def campioni_studio_corrente() -> list[Campione]:
    """I campioni di ogni fascicolo dello studio già presente in `g`, archiviati compresi."""
    from web.helpers import get_fascicoli
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

    repository = build_document_ai_service().repository
    tenant_id = document_ai_tenant_id()
    campioni: list[Campione] = []
    for fascicolo in get_fascicoli().tutti(archiviati=True):
        fascicolo_id = str(getattr(fascicolo, "id", "") or "")
        try:
            assegnazioni = repository.list_catalog_assignments(tenant_id, fascicolo_id)
            eventi = repository.list_catalog_decision_events(tenant_id, fascicolo_id)
        except Exception:  # un fascicolo senza catalogo SQL non ferma la misura
            logger.debug("Catalogo non disponibile per il classificatore di %s", fascicolo_id, exc_info=True)
            continue
        decise = {e.document_id: e.etichetta for e in etichette_dalle_decisioni(assegnazioni, conferme_massive=conferme_massive(eventi))
                  if not e.negativa}
        for assegnazione in assegnazioni:
            try:
                testo = _testo(repository, tenant_id, assegnazione)
            except Exception:
                logger.debug("Testo non disponibile per il classificatore", exc_info=True)
                testo = ""
            documento = str(getattr(assegnazione, "document_id", "") or "")
            campioni.append(Campione(
                document_id=documento, fascicolo_id=fascicolo_id, testo=testo,
                voce=str(getattr(assegnazione, "document_label", "") or ""),
                confidenza=int(getattr(assegnazione, "confidence", 0) or 0),
                stato=str(getattr(assegnazione, "status", "") or ""),
                origine=str(getattr(assegnazione, "source_state", "") or ""),
                voce_avvocato=decise.get(documento, ""),
            ))
    return campioni


def _salva_disaccordi(disaccordi: list[dict[str, Any]]) -> None:
    from web.helpers import get_fascicoli

    cartella = Path(get_fascicoli().db_path).resolve().parent.parent / "intelligence"
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / FILE_DISACCORDI
    provvisorio = destinazione.with_suffix(".tmp")
    provvisorio.write_text(json.dumps(disaccordi, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(provvisorio, destinazione)


def classificatore_studi(app: Flask, *, minimo_per_voce: int = 30) -> dict[str, Any]:
    """Il riepilogo della misura per ogni studio attivo; solo conteggi, nessun dato del cliente."""
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    def uno() -> dict[str, Any]:
        esito = misura(campioni_studio_corrente(), minimo=minimo_per_voce)
        _salva_disaccordi(esito["disaccordi"])
        return esito["riepilogo"]

    risultato: dict[str, Any] = {"studi": {}}
    studi = _active_tenants(app)
    if studi:
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for numero, studio in enumerate(studi, start=1):
            slug = str(getattr(studio, "slug", "") or "").lower()
            with app.test_request_context(f"/__classificatore/catalogo/{slug}"):
                _attach_tenant_context(manager, studio)
                risultato["studi"][f"studio_{numero}"] = uno()
    elif not app.config.get("MULTI_TENANT"):
        with app.test_request_context("/__classificatore/catalogo/default"):
            g.multi_tenant_enabled = False
            risultato["studi"]["studio_1"] = uno()
    return risultato


__all__ = ["FILE_DISACCORDI", "campioni_studio_corrente", "classificatore_studi"]
