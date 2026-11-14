"""Lo stato della pratica, da una sola fonte: il record del fascicolo.

Perché il record e non la regia del deposito: lo stato operativo della regia (es. «FASCICOLO_APERTO») descrive il
percorso del deposito telematico, non la vita della causa; il record del fascicolo è invece quello che l'avvocato
o la lettura della sentenza aggiornano (``stato`` DEFINITO con la data di chiusura e la nota della sentenza in
``avanzamento``; ``archivio_pronto``, vero per ogni fascicolo DEFINITO, lo dichiara pronto per l'archivio; ARCHIVIATO
con l'archiviazione). «definita» resta per i dati che arrivano senza ``archivio_pronto``.
La Lettura del fascicolo ricava la propria intestazione dallo stesso record (``pct/fascicolo_lettura/intestazione``):
usarlo qui fa coincidere presidio, Lettura e quadro.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

ETICHETTE = {
    "in_corso": "Pratica in corso",
    "sospesa": "Pratica sospesa",
    "definita": "Pratica definita",
    "da_archiviare": "Definita, da archiviare",
    "archiviata": "Pratica archiviata",
}

_SENTENZA = re.compile(r"\b(sentenza|ordinanza|decreto)\s+n\.?\s*([0-9]+\s*/\s*[0-9]{4})", re.IGNORECASE)


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def _data_it(iso: Any) -> str:
    testo = _testo(iso)[:10]
    return f"{testo[8:10]}/{testo[5:7]}/{testo[:4]}" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", testo) else ""


def codice_stato(stato: Any, *, archivio_pronto: bool = False) -> str:
    valore = _testo(stato).upper()
    if valore == "ARCHIVIATO":
        return "archiviata"
    if valore in {"DEFINITO", "CHIUSO"}:
        return "da_archiviare" if archivio_pronto else "definita"
    if valore == "SOSPESO":
        return "sospesa"
    return "in_corso"


def _provvedimento(avanzamento: Iterable[Mapping[str, Any]]) -> str:
    """Il provvedimento che ha definito la causa, come registrato nel passaggio a DEFINITO."""
    for voce in reversed(list(avanzamento or [])):
        if _testo(voce.get("stato_nuovo")).upper() not in {"DEFINITO", "CHIUSO"}:
            continue
        trovato = _SENTENZA.search(f"{_testo(voce.get('note'))} {_testo(voce.get('descrizione'))}")
        if trovato:
            return f"{trovato.group(1).capitalize()} n. {trovato.group(2).replace(' ', '')}"
    return ""


def stato_pratica(fascicolo: Mapping[str, Any]) -> dict[str, str]:
    """Codice, etichetta e dettaglio dello stato registrato della pratica."""
    codice = codice_stato(fascicolo.get("stato"), archivio_pronto=bool(fascicolo.get("archivio_pronto")))
    dettaglio = ""
    if codice in {"definita", "da_archiviare"}:
        provvedimento = _provvedimento(fascicolo.get("avanzamento") or [])
        data = _data_it(fascicolo.get("data_chiusura"))
        chiusura = f"Chiusura registrata il {data}" if data else ""
        dettaglio = " · ".join(p for p in (provvedimento, chiusura) if p)
        if not dettaglio:
            dettaglio = "Provvedimento che definisce la causa da indicare nel fascicolo"
    elif codice == "archiviata":
        data = _data_it(fascicolo.get("data_archiviazione") or fascicolo.get("data_chiusura"))
        dettaglio = f"Archiviata il {data}" if data else ""
    elif codice == "in_corso":
        data = _data_it(fascicolo.get("data_apertura"))
        dettaglio = f"Aperta il {data}" if data else ""
    return {"codice": codice, "etichetta": ETICHETTE[codice], "dettaglio": dettaglio}


def stato_pratica_da_fascicolo(fascicolo: Any) -> dict[str, str]:
    """Adattatore per l'oggetto Fascicolo dell'archivio."""
    avanzamento = []
    for voce in getattr(fascicolo, "avanzamento", []) or []:
        avanzamento.append(voce if isinstance(voce, Mapping) else
                           {k: getattr(voce, k, "") for k in ("stato_nuovo", "note", "descrizione")})
    return stato_pratica({
        "stato": getattr(fascicolo, "stato", ""), "archivio_pronto": bool(getattr(fascicolo, "archivio_pronto", False)),
        "avanzamento": avanzamento, "data_chiusura": getattr(fascicolo, "data_chiusura", ""),
        "data_apertura": getattr(fascicolo, "data_apertura", ""),
        "data_archiviazione": getattr(getattr(fascicolo, "archivio", None), "data_archiviazione", ""),
    })


__all__ = ["ETICHETTE", "codice_stato", "stato_pratica", "stato_pratica_da_fascicolo"]
