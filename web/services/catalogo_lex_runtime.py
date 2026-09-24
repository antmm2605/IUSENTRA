"""La seconda lettura di Lex, in coda, fuori dalle richieste web.

Gira nello scheduler-worker (processo separato dall'app): un documento per
volta, con parte dei processori, cosi' le pagine dello studio restano pronte
mentre Lex legge. Ogni studio ha la sua coda: le proposte non confermate,
dalle piu' dubbie. Il modello e' locale (Ollama) e i testi non escono dal
server.

Variabili:
- PCT_LEX_CATALOGO=0 spegne la seconda lettura;
- PCT_LEX_CATALOGO_MODELLO sceglie il modello (predefinito qwen3:4b);
- PCT_LEX_CATALOGO_PER_GIRO documenti per giro (predefinito 1);
- PCT_LEX_CATALOGO_THREAD processori usati da Ollama (predefinito 4).
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import Any

from flask import Flask, g

from pct.document_intelligence.catalog_lex import (
    MODELLO_PREDEFINITO,
    EsitoLex,
    applica_esito,
    da_rileggere,
    leggi_con_lex,
    voci_catalogo,
)
from pct.document_intelligence.models import new_id, utc_now

logger = logging.getLogger(__name__)

_PAGINA_CODA = 200
_MODELLI_PRONTI: set[str] = set()


def _attiva() -> bool:
    return os.getenv("PCT_LEX_CATALOGO", "1").strip().lower() not in {"0", "false", "no", "off"} and os.getenv(
        "PCT_LOCAL_AI_ENABLED", "1"
    ).strip().lower() not in {"0", "false", "no", "off"}


def modello_catalogo() -> str:
    return os.getenv("PCT_LEX_CATALOGO_MODELLO", "").strip() or MODELLO_PREDEFINITO


def _intero(nome: str, predefinito: int) -> int:
    try:
        return max(1, int(os.getenv(nome, "") or predefinito))
    except ValueError:
        return predefinito


def _client():
    from pct.local_ai import OllamaHttpClient, _normalize_api_base_url

    return OllamaHttpClient(_normalize_api_base_url(os.getenv("PCT_LOCAL_AI_BASE_URL", "") or "http://ollama:11434/api"))


def _modello_pronto(client: Any, modello: str) -> bool:
    """Il modello c'e' sul server; al primo giro lo scarica (una volta sola)."""
    if modello in _MODELLI_PRONTI:
        return True
    installati = {str(voce.get("name") or voce.get("model") or "") for voce in client.list_models()}
    if modello not in installati and f"{modello}:latest" not in installati:
        logger.info("[lex-catalogo] Download del modello %s per la seconda lettura.", modello)
        client.pull_model(modello)
    _MODELLI_PRONTI.add(modello)
    return True


def generatore(client: Any, modello: str) -> Callable[[str, dict[str, Any]], str]:
    opzioni = {"temperature": 0, "num_ctx": 8192, "num_thread": _intero("PCT_LEX_CATALOGO_THREAD", 4)}

    def genera(domanda: str, schema: dict[str, Any]) -> str:
        risposta = client.generate_completion(
            modello, domanda, response_format=schema, options=opzioni, think=False, keep_alive="15m", timeout=300,
        )
        return str(risposta.get("response") or "")

    return genera


def _contesto_del_fascicolo(fascicolo: Any) -> str:
    parti = [
        str(getattr(fascicolo, "tribunale", "") or ""),
        f"R.G. {getattr(fascicolo, 'numero_rg', '')}/{getattr(fascicolo, 'anno_rg', '')}" if getattr(fascicolo, "numero_rg", "") else "",
        str(getattr(fascicolo, "oggetto", "") or "")[:160],
    ]
    return " · ".join(parte for parte in parti if parte.strip())


def seconda_lettura_studio_corrente(
    *,
    per_giro: int = 1,
    genera: Callable[[str, dict[str, Any]], str] | None = None,
    modello: str | None = None,
) -> dict[str, Any]:
    """Rilegge fino a `per_giro` proposte dello studio gia' presente in `g`."""
    from web.helpers import get_fascicoli
    from web.services.archivio_letture_runtime import testi_indice_archivio
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

    modello = modello or modello_catalogo()
    repository = build_document_ai_service().repository
    tenant_id = document_ai_tenant_id()
    report = {"lette": 0, "scelte": 0, "cambiate": 0, "errori": 0}
    voci = voci_catalogo()
    testi_per_fascicolo: dict[str, dict[str, str]] = {}
    offset = 0
    while report["lette"] < per_giro:
        pagina = repository.list_catalog_assignments_to_reread(tenant_id, limit=_PAGINA_CODA, offset=offset)
        if not pagina:
            break
        offset += len(pagina)
        for assignment in pagina:
            if report["lette"] >= per_giro:
                break
            if not da_rileggere(assignment, modello=modello):
                continue
            fascicolo = get_fascicoli().get(assignment.fascicolo_id)
            if fascicolo is None:
                continue
            if assignment.fascicolo_id not in testi_per_fascicolo:
                testi_per_fascicolo[assignment.fascicolo_id] = testi_indice_archivio(fascicolo)
            testo = testi_per_fascicolo[assignment.fascicolo_id].get(assignment.document_id, "")
            inizio = time.monotonic()
            if not testo.strip():
                esito = EsitoLex("senza_testo")
            else:
                if genera is None:
                    client = _client()
                    _modello_pronto(client, modello)
                    genera = generatore(client, modello)
                esito = leggi_con_lex(
                    testo, genera=genera, voci=voci,
                    # nessuna proposta nella domanda: un modello piccolo tende a confermarla
                    contesto=_contesto_del_fascicolo(fascicolo),
                )
            durata = time.monotonic() - inizio
            if esito.stato == "errore" and not esito.etichetta:
                # Ollama non raggiungibile: si riprova al prossimo giro, senza segnare il documento.
                report["errori"] += 1
                logger.warning("[lex-catalogo] Seconda lettura non riuscita: %s", esito.motivo)
                return report
            candidati = repository.list_catalog_candidates(assignment.id)
            evidenze = repository.list_catalog_evidence(assignment.id)
            nuova, candidati, evidenze = applica_esito(assignment, candidati, evidenze, esito, modello=modello, durata_s=durata)
            repository.save_catalog_assignment(nuova, candidates=candidati, evidence=evidenze)
            repository.append_audit_event({
                "id": new_id("catalog-audit"), "tenant_id": tenant_id, "fascicolo_id": assignment.fascicolo_id,
                "document_id": assignment.document_id, "version_id": assignment.document_version_id, "user_id": "lex",
                "event_type": "document_catalog.lex_second_reading", "timestamp": utc_now(),
                "sha256": assignment.document_sha256, "filename": str((assignment.metadata or {}).get("filename") or ""),
                "status": nuova.status,
                "payload": {"esito": esito.stato, "etichetta": esito.etichetta, "modello": modello, "durata_s": round(durata, 1)},
            })
            report["lette"] += 1
            report["scelte"] += int(esito.stato == "scelta")
            report["cambiate"] += int(nuova.document_label != assignment.document_label or nuova.status != assignment.status)
    return report


def seconda_lettura_catalogo(app: Flask) -> dict[str, Any]:
    """Un giro della coda per tutti gli studi attivi (scheduler-worker)."""
    if not _attiva():
        return {"attiva": False}
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    per_giro = _intero("PCT_LEX_CATALOGO_PER_GIRO", 1)
    totale = {"attiva": True, "lette": 0, "scelte": 0, "cambiate": 0, "errori": 0}
    studi = _active_tenants(app)
    if studi:
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for studio in studi:
            if totale["lette"] >= per_giro:
                break
            slug = str(getattr(studio, "slug", "") or "").lower()
            with app.test_request_context(f"/__scheduler/catalogo-lex/{slug}"):
                _attach_tenant_context(manager, studio)
                parziale = seconda_lettura_studio_corrente(per_giro=per_giro - totale["lette"])
            for chiave in ("lette", "scelte", "cambiate", "errori"):
                totale[chiave] += int(parziale.get(chiave) or 0)
            if parziale.get("errori"):
                break
    elif not app.config.get("MULTI_TENANT"):
        with app.test_request_context("/__scheduler/catalogo-lex/default"):
            g.multi_tenant_enabled = False
            parziale = seconda_lettura_studio_corrente(per_giro=per_giro)
        for chiave in ("lette", "scelte", "cambiate", "errori"):
            totale[chiave] += int(parziale.get(chiave) or 0)
    return totale


__all__ = ["modello_catalogo", "seconda_lettura_catalogo", "seconda_lettura_studio_corrente"]
