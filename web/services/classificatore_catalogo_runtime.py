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
from pct.document_intelligence.verita.pseudonimi import CAMPI_PERSONE, parole_da_nascondere
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


def _voce_spark(assegnazione) -> str:
    lettura = dict((getattr(assegnazione, "metadata", None) or {}).get("lex_lettura") or {})
    return str(lettura.get("etichetta") or "") if lettura.get("stato") == "scelta" else ""


def campioni_studio_corrente() -> list[Campione]:
    """I campioni di ogni fascicolo dello studio già presente in `g`, archiviati compresi."""
    from web.helpers import get_fascicoli
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

    repository = build_document_ai_service().repository
    tenant_id = document_ai_tenant_id()
    campioni: list[Campione] = []
    for fascicolo in get_fascicoli().tutti(archiviati=True):
        fascicolo_id = str(getattr(fascicolo, "id", "") or "")
        nomi = frozenset(parole_da_nascondere(str(getattr(fascicolo, campo, "") or "") for campo in CAMPI_PERSONE))
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
                voce_spark=_voce_spark(assegnazione), nomi=nomi,
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


CARTELLA_ADDESTRAMENTO = "addestramento_catalogo"


def _scrivi_privato(percorso: Path, contenuto: bytes) -> None:
    provvisorio = percorso.with_suffix(percorso.suffix + ".tmp")
    descrittore = os.open(provvisorio, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descrittore, "wb") as uscita:
        uscita.write(contenuto)
    os.replace(provvisorio, percorso)


def esporta_studio_corrente(*, per_voce_inventati: int = 60) -> dict[str, Any]:
    """Scrive nella cartella dello studio il pacchetto per l'addestramento sul PC dell'avvocato.

    `pacchetto/` contiene solo testi pseudonimizzati, esempi inventati, il prefisso della domanda e il manifesto;
    la corrispondenza codice → documento resta fuori dal pacchetto e non va copiata.
    """
    import gzip

    from pct.document_intelligence.catalog_lex import domanda, voci_catalogo
    from pct.document_intelligence.verita.esportazione import righe_dataset
    from pct.document_intelligence.verita.sintetici import SEME_BANCO, documenti_inventati
    from web.helpers import get_fascicoli

    voci = voci_catalogo()
    etichette = {voce.label for voce in voci}
    righe, corrispondenze, manifesto = righe_dataset(
        campioni_studio_corrente(), documenti_inventati(per_voce_inventati, voci=etichette), etichette,
        banco=documenti_inventati(10, voci=etichette, seme=SEME_BANCO))
    radice = Path(get_fascicoli().db_path).resolve().parent.parent / "intelligence" / CARTELLA_ADDESTRAMENTO
    pacchetto = radice / "pacchetto"
    pacchetto.mkdir(parents=True, exist_ok=True, mode=0o700)
    dataset = "\n".join(json.dumps(riga, ensure_ascii=False) for riga in righe).encode("utf-8")
    _scrivi_privato(pacchetto / "dataset.jsonl.gz", gzip.compress(dataset, mtime=0))
    _scrivi_privato(pacchetto / "prefisso_domanda.txt", domanda("", voci).encode("utf-8"))
    _scrivi_privato(pacchetto / "manifesto.json", json.dumps(manifesto, ensure_ascii=False, indent=1).encode("utf-8"))
    _scrivi_privato(radice / "corrispondenze.json", json.dumps(corrispondenze).encode("utf-8"))
    return {**manifesto, "cartella_pacchetto": str(pacchetto)}


def esportazione_studi(app: Flask) -> dict[str, Any]:
    """Il pacchetto di addestramento di ogni studio attivo; restituisce solo conteggi e percorsi."""
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    risultato: dict[str, Any] = {"studi": {}}
    studi = _active_tenants(app)
    if studi:
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for numero, studio in enumerate(studi, start=1):
            slug = str(getattr(studio, "slug", "") or "").lower()
            with app.test_request_context(f"/__classificatore/esportazione/{slug}"):
                _attach_tenant_context(manager, studio)
                risultato["studi"][f"studio_{numero}"] = esporta_studio_corrente()
    elif not app.config.get("MULTI_TENANT"):
        with app.test_request_context("/__classificatore/esportazione/default"):
            g.multi_tenant_enabled = False
            risultato["studi"]["studio_1"] = esporta_studio_corrente()
    return risultato


__all__ = ["CARTELLA_ADDESTRAMENTO", "FILE_DISACCORDI", "campioni_studio_corrente", "classificatore_studi",
           "esporta_studio_corrente", "esportazione_studi"]
