"""I prospetti a tabella del fascicolo, dall'archivio delle letture (nessuna rilettura).

Il motore documenti conserva ogni prospetto (nota spese, liquidazione,
proforma, precetto, interessi) con la tabella intera e la prova dei conti:
qui si consultano, con il nome del documento da cui vengono.
"""

from __future__ import annotations

from typing import Any


def prospetti_fascicolo(fascicolo: Any) -> list[dict[str, Any]]:
    from pct.archivio_letture.presidi import prospetti_letti
    from web.services.archivio_letture_runtime import fatti_fascicolo

    nomi = {str(getattr(d, "id", "") or ""): str(getattr(d, "nome", "") or "") for d in list(getattr(fascicolo, "documenti", []) or [])}
    voci = prospetti_letti(fatti_fascicolo(fascicolo, categoria="importo"))
    for voce in voci:
        voce["documento"] = nomi.get(str(voce.get("documentoId") or ""), "") or "Documento del fascicolo"
    # I conti che non tornano per primi: sono quelli da guardare.
    return sorted(voci, key=lambda voce: (voce["somma"] != "errore", voce["documento"], voce["pagina"]))


__all__ = ["prospetti_fascicolo"]
