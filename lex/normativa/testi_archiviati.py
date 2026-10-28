"""Compressione lossless del solo archivio storico, separato dagli indici FTS.

Le impronte continuano a coprire il testo UTF-8 originale. Il lettore restituisce
sempre l'intero testo; nessuna sintesi o riduzione del contenuto giuridico.
Le stringhe delle edizioni precedenti restano leggibili senza conversione.
"""
from __future__ import annotations

import zlib

MAGIC = b"IUNORMZ1\0"
MAX_BYTES = 1_000_000_000  # limite nativo SQLite predefinito, non un taglio del testo
CODEC = "iusentra-zlib-utf8-v1"


def archivia_testo(testo: str) -> str | bytes:
    if not isinstance(testo,str):
        raise TypeError("Testo sorgente richiesto come stringa")
    raw=testo.encode("utf-8")
    if len(raw)>MAX_BYTES:
        raise ValueError("Testo oltre il limite dello storage: conservare la fonte originale")
    if len(raw)<256:
        return testo
    packed=MAGIC+len(raw).to_bytes(8,"big")+zlib.compress(raw,level=6)
    return packed if len(packed)<len(raw) else testo


def leggi_testo(valore: str | bytes) -> str:
    if isinstance(valore,str):
        return valore
    if not isinstance(valore,bytes) or not valore.startswith(MAGIC) or len(valore)<len(MAGIC)+8:
        raise ValueError("Formato del testo archiviato non riconosciuto")
    size=int.from_bytes(valore[len(MAGIC):len(MAGIC)+8],"big")
    if size>MAX_BYTES:
        raise ValueError("Dimensione dichiarata del testo archiviato non ammessa")
    decoder=zlib.decompressobj()
    try:
        raw=decoder.decompress(valore[len(MAGIC)+8:],size+1)
        if len(raw)!=size or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            raise ValueError("Testo archiviato incompleto o con dati aggiunti")
        return raw.decode("utf-8",errors="strict")
    except (zlib.error,UnicodeError) as exc:
        raise ValueError("Testo archiviato alterato o non UTF-8") from exc
