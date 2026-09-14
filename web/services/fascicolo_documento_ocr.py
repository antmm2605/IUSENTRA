"""Documenti del fascicolo come sorgente per il riconoscimento del testo.

L'avvocato che vuole il testo di un atto lo ha gia' nel fascicolo: chiedergli di
scaricarlo e ricaricarlo sarebbe lavoro inutile e una copia in piu' del
documento di un cliente sul suo computer. Qui il fascicolo diventa una sorgente
diretta: si elencano i documenti leggibili e si consegnano i byte in chiaro al
riconoscimento, senza scriverli da nessuna parte.

Il modulo non decide nulla sul riconoscimento (quello e' in
`document_ocr_documento`) e non conosce Flask: riceve i gestori e restituisce
dati. Cosi' la stessa lettura vale per la pagina React, per un job e per i test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pct.document_crypto import decrypt_doc
from web.services.document_ocr_documento import ESTENSIONI_RICONOSCIBILI, riconoscibile
from web.services.document_tools import DocumentToolError

# Elenco di scelta, non archivio: oltre questa soglia la tendina non si legge
# piu' e il documento si cerca dal fascicolo.
MAX_DOCUMENTI_ELENCO = 300


def _nome_documento(documento: Any, percorso: Path | None = None) -> str:
    for candidato in (
        getattr(documento, "nome", ""),
        getattr(documento, "nome_originale", ""),
        getattr(documento, "nome_portale", ""),
        percorso.name if percorso is not None else "",
    ):
        testo = str(candidato or "").strip()
        if testo:
            return testo
    return "Documento"


def _estensione_nota(documento: Any) -> str:
    """Prima estensione riconoscibile fra nome visibile e nome del file caricato."""
    for candidato in (
        getattr(documento, "nome", ""),
        getattr(documento, "nome_originale", ""),
        getattr(documento, "nome_portale", ""),
    ):
        suffisso = Path(str(candidato or "").strip()).suffix.lower()
        if suffisso in ESTENSIONI_RICONOSCIBILI:
            return suffisso
    return ""


def _etichetta_dimensione(byte: int) -> str:
    if byte <= 0:
        return ""
    if byte < 1024 * 1024:
        return f"{max(1, round(byte / 1024))} KB"
    return f"{byte / (1024 * 1024):.1f} MB".replace(".", ",")


def documenti_riconoscibili(gestore_fascicoli: Any, fascicolo_id: str) -> list[dict[str, Any]]:
    """Documenti del fascicolo su cui il riconoscimento del testo puo' lavorare.

    I formati non leggibili (fogli di calcolo, buste XML, archivi) non vengono
    elencati: offrirli significherebbe far scegliere all'avvocato una strada che
    finisce in un messaggio di errore.
    """
    try:
        fascicolo = gestore_fascicoli.get(fascicolo_id)
    except Exception as exc:
        raise DocumentToolError("Fascicolo non trovato.") from exc
    if fascicolo is None:
        raise DocumentToolError("Fascicolo non trovato.")

    voci: list[dict[str, Any]] = []
    for documento in list(getattr(fascicolo, "documenti", []) or []):
        nome = _nome_documento(documento)
        suffisso = _estensione_nota(documento)
        if not suffisso and not riconoscibile(nome):
            continue
        dimensione = int(getattr(documento, "dimensione_bytes", 0) or 0)
        voci.append(
            {
                "id": str(getattr(documento, "id", "") or ""),
                "nome": nome,
                "formato": (suffisso or Path(nome).suffix.lower()).lstrip("."),
                "sezione": str(getattr(documento, "sezione", "") or ""),
                "tipo": str(getattr(documento, "tipo", "") or ""),
                "data": str(getattr(documento, "data_documento", "") or getattr(documento, "data_caricamento", "") or ""),
                "dimensione_bytes": dimensione,
                "dimensione": _etichetta_dimensione(dimensione),
                "firmato": bool(
                    getattr(documento, "firmato_digitalmente", False) or getattr(documento, "firmato", False)
                ),
            }
        )
        if len(voci) >= MAX_DOCUMENTI_ELENCO:
            break
    return voci


def leggi_documento(gestore_fascicoli: Any, fascicolo_id: str, documento_id: str) -> tuple[str, bytes]:
    """Nome e contenuto in chiaro del documento, pronti per il riconoscimento."""
    identificativo = str(documento_id or "").strip()
    if not identificativo:
        raise DocumentToolError("Nessun documento selezionato.")
    try:
        fascicolo = gestore_fascicoli.get(fascicolo_id)
    except Exception as exc:
        raise DocumentToolError("Fascicolo non trovato.") from exc
    if fascicolo is None:
        raise DocumentToolError("Fascicolo non trovato.")
    documento = next(
        (voce for voce in (getattr(fascicolo, "documenti", []) or []) if str(getattr(voce, "id", "")) == identificativo),
        None,
    )
    if documento is None:
        raise DocumentToolError("Documento non presente in questo fascicolo.")

    risolutore = getattr(gestore_fascicoli, "percorso_documento_lettura", None)
    if not callable(risolutore):
        risolutore = getattr(gestore_fascicoli, "percorso_documento", None)
    if not callable(risolutore):
        raise DocumentToolError("Documento non leggibile in questa installazione.")
    percorso = Path(risolutore(fascicolo_id, identificativo))
    try:
        contenuto = decrypt_doc(percorso.read_bytes())
    except FileNotFoundError as exc:
        raise DocumentToolError("Il file del documento non è più presente sul server.") from exc
    except Exception as exc:
        raise DocumentToolError("Il documento non è leggibile: riprova o scaricalo per controllarlo.") from exc

    nome = _nome_documento(documento, percorso)
    if not riconoscibile(nome):
        # Il titolo del documento puo' non riportare l'estensione: vale il file.
        nome = f"{nome}{percorso.suffix.lower()}" if riconoscibile(percorso.name) else nome
    if not riconoscibile(nome):
        raise DocumentToolError(
            "Formato non riconoscibile: il riconoscimento del testo funziona su PDF, immagini e atti firmati .p7m."
        )
    return nome, contenuto


__all__ = ["MAX_DOCUMENTI_ELENCO", "documenti_riconoscibili", "leggi_documento"]
