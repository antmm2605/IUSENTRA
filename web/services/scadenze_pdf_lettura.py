"""Scadenze lette dai PDF dei fascicoli: lettura in sfondo, anteprima dall'archivio.

La pagina Scadenziario apriva e leggeva i PDF di tutti i fascicoli dentro la
richiesta dell'avvocato, con un limite di tempo che fermava la scansione a metà.
Ora ogni PDF si legge una volta sola, in sfondo, e le scadenze trovate si
conservano nel registro delle letture (lettore `scadenze_pdf`, impronta del
documento): l'anteprima le prende dal registro senza aprire file e, se qualche
documento è nuovo o cambiato, avvia la lettura in sfondo e lo dichiara
(`summary.pending`). Il client ripete l'anteprima finché la lettura non finisce.

Base normativa: art. 3 D.M. 44/2011 e art. 20 CAD (impronta e integrità dei
documenti informatici); regola del registro delle letture (CLAUDE.md).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import fields
from typing import Any

from flask import current_app, g, has_request_context

from web.services import pdf_deadline_import as pdf

logger = logging.getLogger(__name__)

LETTORE = "scadenze_pdf"
VERSIONE = "scadenze-pdf.v1"

_LOCK = threading.Lock()
_IN_CORSO: dict[str, int] = {}
_CAMPI_CANDIDATO = {f.name for f in fields(pdf.PdfDeadlineCandidate)}


def _tenant() -> str:
    from web.services.registro_letture_runtime import tenant_corrente

    return tenant_corrente()


def _documenti_pdf(gestione_fascicoli: Any, fascicolo: Any) -> list[tuple[Any, Any, Any]]:
    """(documento, percorso, oggetto del registro) dei PDF presenti, senza aprire i file."""
    from pct.registro_letture.inventario import oggetto_da_documento
    from web.services.registro_letture_runtime import cifratura_attiva

    cifrati = cifratura_attiva()
    righe = []
    for documento in list(getattr(fascicolo, "documenti", []) or []):
        percorso = pdf._document_path(gestione_fascicoli, fascicolo, documento)
        if not pdf._is_pdf_document(documento, percorso):
            continue
        oggetto = oggetto_da_documento(documento, fascicolo, cifratura_attiva=cifrati)
        if oggetto is not None:
            righe.append((documento, percorso, oggetto))
    return righe


def _candidati_registrati(registro: Any, tenant: str, fascicolo_id: str) -> dict[tuple[str, str], list[dict[str, Any]]]:
    letti: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for lettura in registro.letture(tenant, fascicolo_id, lettore=LETTORE):
        if lettura.stato != "letto" or lettura.versione_lettore != VERSIONE:
            continue
        letti[(lettura.oggetto_id, lettura.sha256)] = list((lettura.esito or {}).get("candidati") or [])
    return letti


def _candidato(dati: dict[str, Any], markers: dict[str, str], semantic: dict[str, str]) -> pdf.PdfDeadlineCandidate:
    candidato = pdf.PdfDeadlineCandidate(**{k: v for k, v in dati.items() if k in _CAMPI_CANDIDATO})
    esistente = markers.get(candidato.id, "") or semantic.get(candidato.semantic_key, "")
    candidato.duplicate = bool(esistente)
    candidato.existing_deadline_id = esistente
    candidato.selected = not candidato.duplicate and candidato.confidence >= 0.68
    return candidato


def leggi_documento(registro: Any, tenant: str, fascicolo: Any, documento: Any, percorso: Any, oggetto: Any) -> int:
    """Legge un PDF e registra le scadenze trovate (anche nessuna) con l'impronta del documento."""
    try:
        candidati = pdf._candidates_from_document(
            fascicolo=fascicolo, documento=documento, path=percorso, existing_markers={}, existing_semantic={},
        )
        stato, esito = "letto", {"candidati": [c.to_dict() for c in candidati]}
    except Exception as exc:  # un PDF illeggibile non ferma gli altri
        logger.warning("Scadenze PDF: documento %s non letto: %s", getattr(documento, "id", ""), exc)
        candidati, stato, esito = [], "letto", {"candidati": [], "errore": "documento non leggibile"}
    registro.segna_letto(tenant, str(fascicolo.id), oggetto, LETTORE, versione=VERSIONE, stato=stato, esito=esito)
    return len(candidati)


def _avvia_in_sfondo(fascicoli_ids: list[str]) -> bool:
    """Una sola lettura per studio alla volta; legge i PDF mancanti dei fascicoli indicati."""
    if not has_request_context():
        return False
    tenant = _tenant()
    with _LOCK:
        if _IN_CORSO.get(tenant):
            return True
        _IN_CORSO[tenant] = 1
    app = current_app._get_current_object()
    percorsi = dict(getattr(g, "data_paths", {}) or {})
    contesto = {
        "tenant": getattr(g, "tenant", None),
        "tenant_context_slug": getattr(g, "tenant_context_slug", ""),
        "multi_tenant_enabled": getattr(g, "multi_tenant_enabled", False),
    }

    def corsa() -> None:
        try:
            with app.test_request_context("/__scadenze-pdf"):
                g.data_paths = percorsi
                g.tenant = contesto["tenant"]
                g.tenant_context_slug = contesto["tenant_context_slug"]
                g.multi_tenant_enabled = contesto["multi_tenant_enabled"]
                g.tenant_context_required = False
                g.tenant_context_missing = False
                from web.helpers import get_fascicoli
                from web.services.registro_letture_runtime import registro_corrente

                gestione = get_fascicoli()
                registro = registro_corrente()
                for fascicolo_id in fascicoli_ids:
                    fascicolo = gestione.get(fascicolo_id)
                    if fascicolo is None:
                        continue
                    letti = _candidati_registrati(registro, tenant, fascicolo_id)
                    for documento, percorso, oggetto in _documenti_pdf(gestione, fascicolo):
                        if (oggetto.oggetto_id, oggetto.impronta) in letti:
                            continue
                        leggi_documento(registro, tenant, fascicolo, documento, percorso, oggetto)
        except Exception:
            logger.exception("Lettura in sfondo delle scadenze PDF interrotta")
        finally:
            with _LOCK:
                _IN_CORSO.pop(tenant, None)

    threading.Thread(target=corsa, name=f"scadenze-pdf-{tenant}", daemon=True).start()
    return True


def lettura_in_corso() -> bool:
    try:
        return bool(_IN_CORSO.get(_tenant()))
    except Exception:
        return False


def anteprima(
    *,
    gestione_fascicoli: Any,
    gestione_scadenziario: Any,
    id_fascicolo: str = "",
    avvia_lettura: bool = True,
) -> dict[str, Any]:
    """Le scadenze già lette dai PDF, senza aprire file; i PDF nuovi si leggono in sfondo."""
    from web.services.registro_letture_runtime import registro_corrente

    registro = registro_corrente()
    tenant = _tenant()
    fascicoli = pdf._fascicoli_da_scansionare(gestione_fascicoli, id_fascicolo)
    markers, semantic = pdf._existing_import_markers(gestione_scadenziario)
    candidati: list[pdf.PdfDeadlineCandidate] = []
    letti = da_leggere = 0
    con_mancanti: list[str] = []
    for fascicolo in fascicoli:
        fascicolo_id = str(getattr(fascicolo, "id", "") or "")
        registrati = _candidati_registrati(registro, tenant, fascicolo_id)
        mancanti = 0
        for _documento, _percorso, oggetto in _documenti_pdf(gestione_fascicoli, fascicolo):
            chiave = (oggetto.oggetto_id, oggetto.impronta)
            if chiave in registrati:
                letti += 1
                candidati.extend(_candidato(dati, markers, semantic) for dati in registrati[chiave])
            else:
                mancanti += 1
        if mancanti:
            da_leggere += mancanti
            con_mancanti.append(fascicolo_id)
    candidati = pdf._deduplicate_candidates(candidati)
    candidati.sort(key=lambda item: (item.duplicate, item.due_date, item.fascicolo_label, item.document_name))
    avviata = bool(con_mancanti) and avvia_lettura and _avvia_in_sfondo(con_mancanti)
    avvisi = []
    if da_leggere:
        avvisi.append(
            f"{da_leggere} PDF ancora da leggere: la lettura prosegue in sfondo e l'elenco si aggiorna da solo."
            if avviata else f"{da_leggere} PDF ancora da leggere."
        )
    risultato = pdf.PdfDeadlinePreview(candidati, len(fascicoli), letti, 0, avvisi).to_dict()
    risultato["summary"]["pending"] = da_leggere
    risultato["summary"]["scanning"] = bool(da_leggere and (avviata or lettura_in_corso()))
    return risultato


def candidati_per_import(*, gestione_fascicoli: Any, gestione_scadenziario: Any, id_fascicolo: str = "") -> list[pdf.PdfDeadlineCandidate]:
    """Per l'importazione: gli stessi candidati dell'anteprima, dal registro."""
    esito = anteprima(
        gestione_fascicoli=gestione_fascicoli,
        gestione_scadenziario=gestione_scadenziario,
        id_fascicolo=id_fascicolo,
        avvia_lettura=False,
    )
    return [pdf.PdfDeadlineCandidate(**{k: v for k, v in c.items() if k in _CAMPI_CANDIDATO}) for c in esito["candidates"]]


__all__ = ["LETTORE", "VERSIONE", "anteprima", "candidati_per_import", "leggi_documento", "lettura_in_corso"]
