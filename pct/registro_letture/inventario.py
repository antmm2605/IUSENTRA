"""L'inventario del fascicolo: gli oggetti che i lettori devono conoscere.

Funzioni pure: ricevono il fascicolo e le righe PEC già lette, non aprono file
né database. Le chiavi di associazione — nome e cognome del cliente, numero e
anno di ruolo — viaggiano con ogni oggetto, così il registro sa a chi
appartiene ciò che ha letto anche quando lo consulta fuori dal fascicolo.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from .modello import Oggetto

_HEX64 = 64


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _sha(valore: Any) -> str:
    sha = _testo(valore).lower()
    return sha if len(sha) == _HEX64 and all(c in "0123456789abcdef" for c in sha) else ""


def _campo(oggetto: Any, *nomi: str) -> Any:
    for nome in nomi:
        if isinstance(oggetto, dict):
            if nome in oggetto and oggetto[nome] not in (None, ""):
                return oggetto[nome]
        elif getattr(oggetto, nome, None) not in (None, ""):
            return getattr(oggetto, nome)
    return ""


def chiavi_fascicolo(fascicolo: Any) -> dict[str, str]:
    """Cliente, numero e anno di ruolo del fascicolo, come stringhe pulite."""
    return {
        "cliente": _testo(_campo(fascicolo, "nome_cliente")),
        "numero_rg": _testo(_campo(fascicolo, "numero_rg")),
        "anno_rg": _testo(_campo(fascicolo, "anno_rg")),
    }


def oggetto_da_documento(documento: Any, fascicolo: Any, *, cifratura_attiva: bool = True) -> Oggetto | None:
    """Un documento del fascicolo come oggetto del registro, senza aprire il file.

    `hash_contenuto_sha256` è l'impronta del contenuto in chiaro quando differisce
    dall'impronta del file conservato o quando i documenti non sono cifrati;
    altrimenti l'impronta in chiaro non è nota e resta da imparare alla prima
    lettura (il registro la memorizza per il file conservato).
    """
    identificativo = _testo(_campo(documento, "id"))
    if not identificativo or _testo(_campo(documento, "eliminato_il")):
        return None
    archivio = _sha(_campo(documento, "hash_sha256"))
    contenuto = _sha(_campo(documento, "hash_contenuto_sha256"))
    if contenuto and (contenuto != archivio or not cifratura_attiva):
        sha = contenuto
    elif not cifratura_attiva:
        sha = archivio
    else:
        sha = ""
    chiavi = chiavi_fascicolo(fascicolo)
    tipo = _campo(documento, "tipo")
    tipo = getattr(tipo, "value", tipo)
    return Oggetto(
        tipo="documento",
        oggetto_id=identificativo,
        nome=_testo(_campo(documento, "nome")),
        sha256=sha,
        sha256_archivio=archivio,
        dimensione=int(_campo(documento, "dimensione_bytes") or 0),
        origine=_testo(_campo(documento, "fonte_documento")) or _testo(tipo),
        data_oggetto=_testo(_campo(documento, "data_documento", "data_deposito_portale", "data_caricamento"))[:10],
        **chiavi,
    )


def oggetti_da_fascicolo(fascicolo: Any, *, cifratura_attiva: bool = True) -> list[Oggetto]:
    oggetti: list[Oggetto] = []
    for documento in list(_campo(fascicolo, "documenti") or []):
        oggetto = oggetto_da_documento(documento, fascicolo, cifratura_attiva=cifratura_attiva)
        if oggetto is not None:
            oggetti.append(oggetto)
    return oggetti


def oggetti_da_pec(righe: Iterable[dict[str, Any]], fascicolo: Any) -> list[Oggetto]:
    """I messaggi PEC collegati al fascicolo e i loro allegati, dalle righe del presidio.

    Ogni riga porta `id`, `mime_sha256`, `received_at`, `metadata_json` e, se
    presenti, `allegati` (`id`, `filename`, `sha256`, `size_bytes`).
    """
    chiavi = chiavi_fascicolo(fascicolo)
    oggetti: list[Oggetto] = []
    for riga in righe:
        identificativo = _testo(riga.get("id"))
        if not identificativo:
            continue
        try:
            metadata = json.loads(riga.get("metadata_json") or "{}")
        except (TypeError, ValueError):
            metadata = {}
        intestazioni = dict(metadata.get("headers") or {}) if isinstance(metadata, dict) else {}
        oggetti.append(Oggetto(
            tipo="pec",
            oggetto_id=identificativo,
            nome=_testo(intestazioni.get("subject")) or "PEC senza oggetto",
            sha256=_sha(riga.get("mime_sha256")),
            dimensione=int(riga.get("mime_size") or 0),
            origine=_testo(intestazioni.get("from")),
            data_oggetto=_testo(riga.get("received_at"))[:10],
            **chiavi,
        ))
        for allegato in list(riga.get("allegati") or []):
            allegato_id = _testo(allegato.get("id")) or f"{identificativo}:{allegato.get('attachment_index', '')}"
            oggetti.append(Oggetto(
                tipo="allegato_pec",
                oggetto_id=allegato_id,
                nome=_testo(allegato.get("filename")),
                sha256=_sha(allegato.get("sha256")),
                dimensione=int(allegato.get("size_bytes") or 0),
                origine=identificativo,
                data_oggetto=_testo(riga.get("received_at"))[:10],
                **chiavi,
            ))
    return oggetti


__all__ = ["chiavi_fascicolo", "oggetti_da_fascicolo", "oggetti_da_pec", "oggetto_da_documento"]
