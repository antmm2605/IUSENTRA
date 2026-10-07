"""Read-only, explicit appointment links for the client folder.

An RG number alone is not an identity: 821 must not match 1821, a
document quotation, or a random identifier. Existing legal workflows
keep their accepted resolver; this projection only governs the folder.
"""
from typing import Any

from web.services.react_fascicoli_bridge import (
    _agenda_for_fascicolo, _canonical_rg_reference, _fascicolo_rg_key,
    _identity_key, _text,
)


def appuntamenti_cartella(agenda: Any, fascicoli: list[Any], cliente_id: str) -> list[Any]:
    linked = {item.id: item for item in agenda.per_cliente(cliente_id)}
    for fascicolo in fascicoli:
        fid = _text(getattr(fascicolo, "id", ""))
        source = _text(getattr(fascicolo, "source_external_id", ""))
        rg = _fascicolo_rg_key(fascicolo)
        client_name = _identity_key(getattr(fascicolo, "nome_cliente", ""))
        court = _identity_key(getattr(fascicolo, "tribunale", ""))
        for item in _agenda_for_fascicolo(lambda: agenda, fascicolo):
            profile = _text(getattr(item, "external_profile_id", ""))
            direct = bool(
                fid and profile == f"fascicolo:{fid}"
                or source and _text(getattr(item, "external_source_url", "")) == source
            )
            if direct:
                linked[item.id] = item
                continue
            item_client = _text(getattr(item, "id_cliente", ""))
            if item_client and item_client != cliente_id:
                continue
            if profile.startswith("fascicolo:") and profile != f"fascicolo:{fid}":
                continue
            item_rg = _canonical_rg_reference(getattr(item, "procedimento", ""))
            same_client = bool(
                item_client == cliente_id
                or client_name and client_name == _identity_key(getattr(item, "cliente", ""))
            )
            same_court = bool(court and court == _identity_key(getattr(item, "tribunale", "")))
            if rg and item_rg == rg and (same_client or same_court):
                linked[item.id] = item
    return list(linked.values())
