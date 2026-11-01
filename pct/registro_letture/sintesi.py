"""La riga di sintesi per fascicolo del registro delle letture.

Una riga per fascicolo con l'identità canonica (cliente, tipo pratica, ufficio, RG, stato e date), quanti
documenti, PEC e allegati sono nell'inventario, l'impronta dell'inventario e, per ogni lettore, quanti oggetti
ha letto, quanti restano, quanti sono in errore, con quale versione e quando ha letto l'ultima volta.

Tutti i motori trovano qui dove andare a leggere: un fascicolo con ``da_leggere = 0`` e impronta invariata
non si riapre. La riga si calcola solo dal registro (nessun file, nessuna PEC): costa due letture SQL.
"""

from __future__ import annotations

import json
from typing import Any

COLONNE_SINTESI = (
    "id", "tenant_id", "fascicolo_id", "id_cliente", "cliente", "tipo_pratica", "ufficio", "numero_rg", "anno_rg",
    "stato", "data_apertura", "data_definizione", "data_archiviazione", "prossima_udienza", "documenti_presenti",
    "pec_collegate", "allegati_pec", "impronta_inventario", "da_leggere", "lettori_json", "aggiornato_il",
)
CAMPI_IDENTITA = (
    "id_cliente", "cliente", "tipo_pratica", "ufficio", "numero_rg", "anno_rg", "stato",
    "data_apertura", "data_definizione", "data_archiviazione", "prossima_udienza",
)


class SintesiMixin:
    """Scrittura e lettura della riga di sintesi (richiede i metodi del RegistroLetture)."""

    def aggiorna_sintesi(self, tenant_id: str, fascicolo_id: str, identita: dict[str, Any]) -> dict[str, Any]:
        tenant, fascicolo = str(tenant_id or "").strip(), str(fascicolo_id or "").strip()
        stato = self.stato_fascicolo(tenant, fascicolo)  # type: ignore[attr-defined]
        oggetti = self.oggetti(tenant, fascicolo)  # type: ignore[attr-defined]
        per_tipo = {tipo: sum(1 for o in oggetti if o.tipo == tipo) for tipo in ("documento", "pec", "allegato_pec")}
        lettori = {
            voce.lettore: {
                "etichetta": voce.etichetta, "versione": voce.versione, "letti": voce.letti,
                "da_leggere": voce.da_leggere, "errori": voce.errori, "ultima_lettura": voce.ultima_lettura,
                "completa": voce.completa,
            }
            for voce in stato.lettori
        }
        valori: dict[str, Any] = {campo: str(identita.get(campo) or "") for campo in CAMPI_IDENTITA}
        valori.update({
            "documenti_presenti": per_tipo["documento"], "pec_collegate": per_tipo["pec"],
            "allegati_pec": per_tipo["allegato_pec"], "impronta_inventario": stato.impronta,
            "da_leggere": sum(int(voce["da_leggere"]) for voce in lettori.values()),
            "lettori_json": json.dumps(lettori, ensure_ascii=False, sort_keys=True),
            "aggiornato_il": self._adesso(),  # type: ignore[attr-defined]
        })
        filtro = "tenant_id = ? AND fascicolo_id = ?"
        with self.connection() as conn:  # type: ignore[attr-defined]
            esistente = conn.execute(
                f"SELECT id FROM {self._tabella('letture_sintesi_fascicolo')} WHERE {self._filtro(filtro)}",  # type: ignore[attr-defined]
                (tenant, fascicolo),
            ).fetchone()
            if esistente:
                self._aggiorna(conn, "letture_sintesi_fascicolo", valori, filtro, (tenant, fascicolo))  # type: ignore[attr-defined]
            else:
                self._inserisci(conn, "letture_sintesi_fascicolo", {  # type: ignore[attr-defined]
                    "id": self._nuovo_id("ls"), "tenant_id": tenant, "fascicolo_id": fascicolo, **valori,  # type: ignore[attr-defined]
                })
        return _riga(valori | {"tenant_id": tenant, "fascicolo_id": fascicolo})

    def sintesi(self, tenant_id: str, fascicolo_id: str) -> dict[str, Any] | None:
        righe = self._seleziona(  # type: ignore[attr-defined]
            "letture_sintesi_fascicolo", "tenant_id = ? AND fascicolo_id = ?",
            (str(tenant_id or "").strip(), str(fascicolo_id or "").strip()),
        )
        return _riga(righe[0]) if righe else None

    def sintesi_studio(self, tenant_id: str) -> list[dict[str, Any]]:
        """Tutti i fascicoli dello studio in una lettura sola, per elenco e panoramica."""
        righe = self._seleziona(  # type: ignore[attr-defined]
            "letture_sintesi_fascicolo", "tenant_id = ?", (str(tenant_id or "").strip(),), ordine="fascicolo_id",
        )
        return [_riga(riga) for riga in righe]


def _riga(valori: dict[str, Any]) -> dict[str, Any]:
    riga = {k: v for k, v in dict(valori).items() if k != "id"}
    grezzo = riga.pop("lettori_json", "{}")
    try:
        riga["lettori"] = json.loads(grezzo) if isinstance(grezzo, str) else dict(grezzo or {})
    except (TypeError, ValueError):
        riga["lettori"] = {}
    for campo in ("documenti_presenti", "pec_collegate", "allegati_pec", "da_leggere"):
        riga[campo] = int(riga.get(campo) or 0)
    return riga


def identita_cambiata(riga: dict[str, Any] | None, identita: dict[str, Any]) -> bool:
    """Vero se la riga manca o se un campo dell'identità è cambiato (stato, date, cliente, ufficio…)."""
    if not riga:
        return True
    return any(str(riga.get(campo) or "") != str(identita.get(campo) or "") for campo in CAMPI_IDENTITA)


__all__ = ["CAMPI_IDENTITA", "COLONNE_SINTESI", "SintesiMixin", "identita_cambiata"]
