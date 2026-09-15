"""La cache breve della Lettura del fascicolo, invalidabile per fascicolo.

La lettura costa qualche decina di millisecondi a caldo ma la pagina la chiede
a ogni apertura: entro il TTL la risposta già serializzata viene riusata. Un
documento caricato, sostituito o rimosso e una PEC collegata invalidano la
voce del fascicolo, così la lettura non mostra mai uno stato superato.
"""

from __future__ import annotations

from web.services.react_payload_cache import ReactPayloadTTLCache

LETTURA_CACHE = ReactPayloadTTLCache(ttl_seconds=20.0, max_entries=64)


def chiave_lettura(tenant_id: str, fascicolo_id: str) -> tuple:
    return ("lettura", str(tenant_id or ""), str(fascicolo_id or ""))


def invalida_lettura(fascicolo_id: str) -> int:
    """Invalida la lettura del fascicolo per qualunque studio: la chiave è per fascicolo."""
    target = str(fascicolo_id or "")
    if not target:
        return 0
    return LETTURA_CACHE.invalidate_where(lambda key: len(key) == 3 and key[0] == "lettura" and key[2] == target)


__all__ = ["LETTURA_CACHE", "chiave_lettura", "invalida_lettura"]
