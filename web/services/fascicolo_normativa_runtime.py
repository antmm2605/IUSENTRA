"""Normativa del fascicolo: raccolta dei dati già presenti e testo dall'archivio Normattiva del server.

Il servizio legge la pratica del tenant attivo, le sue scadenze e le
assegnazioni SQL del catalogo dei documenti, poi delega l'aggregazione al
dominio (`pct.normativa_fascicolo`). Non apre né decifra documenti. Il testo
integrale di un articolo, quando c'è, viene dall'archivio Normattiva importato
sul server (`lex.testi_ufficiali.testo_articolo`), con la sua versione.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from pct.normativa_fascicolo import normativa_del_fascicolo
from web.services.react_payload_cache import ReactPayloadTTLCache

# Cache breve: la pagina si riapre spesso, scadenze e catalogo cambiano di rado.
NORMATIVA_CACHE = ReactPayloadTTLCache(ttl_seconds=60.0, max_entries=128)

_URN = re.compile(r"^urn:nir:[a-z0-9.:;\-]{6,180}$")
_ARTICOLO = re.compile(r"^[0-9]{1,5}[a-z0-9.]{0,24}$")
_TEMPO_CONTROLLO_ARCHIVIO = 1.5  # secondi


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def _dati_fascicolo(fascicolo: Any) -> dict[str, str]:
    campi = ("id", "tipo", "tipo_procedimento", "area_pratica", "canale_operativo", "tribunale", "codice_oggetto_pst")
    return {campo: _testo(getattr(fascicolo, campo, "")) for campo in campi}


def _nomi_documenti(fascicolo: Any) -> dict[str, str]:
    nomi: dict[str, str] = {}
    for documento in list(getattr(fascicolo, "documenti", []) or []):
        identificativo = _testo(getattr(documento, "id", ""))
        if identificativo:
            nomi[identificativo] = _testo(getattr(documento, "nome", "") or getattr(documento, "nome_file", "")) or "documento"
    return nomi


def _catalogo(fascicolo: Any) -> list[Any]:
    from web.services.react_fascicoli_bridge import _sql_document_catalog_by_id

    return list(_sql_document_catalog_by_id(fascicolo).values())


def _richiesta(urn: str, articolo: str):
    from lex.testi_ufficiali import RichiestaArticolo, chiave_articolo

    urn = str(urn or "").strip()
    articolo = str(articolo or "").strip().lower()
    if not _URN.match(urn) or not _ARTICOLO.match(articolo):
        return None
    chiave = chiave_articolo(articolo)
    return RichiestaArticolo(articolo, chiave, "", urn) if chiave else None


def testo_archivio(db: Any, urn: str, articolo: str) -> dict[str, str] | None:
    """Il testo dell'articolo come importato da Normattiva sul server, o None."""
    from lex.testi_ufficiali import testo_articolo

    richiesta = _richiesta(urn, articolo)
    if richiesta is None:
        return None
    trovato = testo_articolo(db, richiesta)
    if not trovato or not str(trovato.get("testo") or "").strip():
        return None
    vigenza = str(trovato.get("vigenza") or "")
    if vigenza.upper() == "EDIZIONE_ACQUISITA":
        vigenza = "edizione acquisita, vigenza attuale non attestata"
    importato = str(trovato.get("importato_il") or "")
    importato_it = "/".join(reversed(importato.split("-"))) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", importato) else ""
    return {
        "testo": str(trovato["testo"]).strip(),
        "versione": vigenza or (f"importata il {importato_it}" if importato_it else "data di importazione non registrata"),
        "importatoIl": importato_it,
        "atto": str(trovato.get("titolo_atto") or ""),
    }


def _segna_testi_in_archivio(payload: dict[str, Any], db: Any) -> None:
    """Indica quali articoli hanno il testo nell'archivio locale (un controllo per norma)."""
    from pathlib import Path

    disponibile = bool(db) and Path(str(db)).is_file()
    # Un archivio molto grande non deve rallentare l'apertura: oltre il tempo concesso la
    # disponibilità resta «da verificare» (None) e il testo si cerca solo se l'avvocato lo chiede.
    limite = time.monotonic() + _TEMPO_CONTROLLO_ARCHIVIO
    visti: dict[tuple[str, str], bool | None] = {}
    for gruppo in payload["gruppi"]:
        for voce in gruppo["voci"]:
            riferimento = voce.get("archivio") or {}
            chiave = (str(riferimento.get("urn") or ""), str(riferimento.get("articolo") or ""))
            if chiave not in visti:
                if not (disponibile and all(chiave)):
                    visti[chiave] = False
                elif time.monotonic() > limite:
                    visti[chiave] = None
                else:
                    visti[chiave] = bool(testo_archivio(db, *chiave))
            voce["testoInArchivio"] = visti[chiave]


def build_normativa_payload(
    fascicolo_id: str, *, carica_fascicolo: Callable[[], Any], scadenziario: Callable[[], Any], archivio_db: Callable[[], Any],
) -> dict[str, Any] | None:
    gestore = carica_fascicolo()
    fascicolo = gestore.get(fascicolo_id) if gestore is not None else None
    if fascicolo is None:
        return None
    try:
        scadenze = list(scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=True))
    except Exception:
        scadenze = []
    try:
        catalogo = _catalogo(fascicolo)
    except Exception:
        catalogo = []
    payload = normativa_del_fascicolo(_dati_fascicolo(fascicolo), scadenze=scadenze, catalogo=catalogo,
                                      nomi_documenti=_nomi_documenti(fascicolo))
    try:
        db = archivio_db()
    except Exception:
        db = None
    _segna_testi_in_archivio(payload, db)
    payload["fascicolo"] = {"id": _testo(getattr(fascicolo, "id", "")), "titolo": _testo(getattr(fascicolo, "titolo", ""))}
    return payload


__all__ = ["NORMATIVA_CACHE", "build_normativa_payload", "testo_archivio"]
