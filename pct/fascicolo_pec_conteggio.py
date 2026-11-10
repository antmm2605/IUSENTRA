"""Un solo conteggio delle PEC del fascicolo, per la Lettura e per il quadro.

La Lettura contava le PEC già collegate («Presidio PEC 0») mentre le verifiche automatiche dicevano «1 messaggi
esaminati, 1 da confermare»: due numeri veri ma diversi, presentati come lo stesso dato. Qui si distinguono:
- collegate: le PEC che riguardano la pratica e sono collegate al fascicolo;
- da_controllare: collegate ma con anomalie da controllare (qualità, termini, udienze);
- da_confermare: PEC che citano il ruolo ma il cui collegamento al fascicolo attende la conferma dell'avvocato
  (identità del procedimento o provenienza dall'ufficio non dimostrate).
"""

from __future__ import annotations

from typing import Any, Mapping


def _quante(valore: Any) -> int:
    if isinstance(valore, (list, tuple, set)):
        return len(valore)
    try:
        return max(0, int(valore or 0))
    except (TypeError, ValueError):
        return 0


def conteggio_pec(pec_letto: Mapping[str, Any] | None, verifiche: Mapping[str, Any] | None = None) -> dict[str, Any]:
    pec_letto = pec_letto or {}
    esito_pec = dict(((verifiche or {}).get("esiti") or {}).get("pec") or {})
    collegate = _quante(pec_letto.get("totale"))
    da_controllare = _quante(pec_letto.get("da_controllare"))
    da_confermare = _quante(esito_pec.get("da_confermare"))
    parti = [f"{collegate} {'PEC collegata' if collegate == 1 else 'PEC collegate'} al fascicolo"]
    if da_controllare:
        parti.append(f"{da_controllare} da controllare")
    if da_confermare:
        parti.append(f"{da_confermare} da confermare il collegamento")
    return {"collegate": collegate, "da_controllare": da_controllare, "da_confermare": da_confermare,
            "esaminate": _quante(esito_pec.get("esaminate")), "testo": " · ".join(parti)}


__all__ = ["conteggio_pec"]
