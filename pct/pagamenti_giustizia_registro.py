"""Uso delle ricevute telematiche pagoPA fra i fascicoli dello studio.

Una ricevuta telematica (RT) prova un solo versamento: lo stesso IUV non può provare il contributo
unificato di due iscrizioni o depositi diversi (vademecum pagamenti PST, stati «disponibile/usato»;
art. 4 c. 9 D.L. 193/2009; D.P.R. 115/2002 art. 13). Qui si cerca se lo IUV di una ricevuta risulta già
collegato ad altri fascicoli dello stesso studio. L'esito è un avviso per l'avvocato: non blocca il
deposito né cambia i controlli della busta.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


def forme_iuv(valore: str) -> set[str]:
    """IUV e numero avviso: il numero avviso a 18 cifre è la cifra ausiliaria seguita dallo IUV."""
    cifre = re.sub(r"\D", "", str(valore or ""))
    if not cifre:
        return set()
    forme = {cifre}
    if len(cifre) == 18:
        forme.add(cifre[1:])
    return forme


def _iuv_del_fascicolo(fascicolo: Any) -> set[str]:
    pagamenti = dict(getattr(fascicolo, "pagamenti", {}) or {})
    trovati: set[str] = set()
    for avviso in (dict(pagamenti.get("pagopa_portale") or {}).get("avvisi") or []):
        if avviso.get("documento_id"):
            trovati |= forme_iuv(avviso.get("iuv") or avviso.get("numero_avviso") or "")
    contributo = dict(pagamenti.get("contributo_unificato") or {})
    if contributo.get("pagato") or contributo.get("status") == "pagato":
        trovati |= forme_iuv(contributo.get("iuv") or "")
    return trovati


def usi_altrove(fascicoli: Iterable[Any], iuv: str, *, escludi: str = "") -> list[dict[str, str]]:
    """Fascicoli (diversi da ``escludi``) in cui lo stesso IUV risulta già usato."""
    cercati = forme_iuv(iuv)
    if not cercati:
        return []
    usi = []
    for fascicolo in fascicoli:
        fid = str(getattr(fascicolo, "id", "") or "")
        if not fid or fid == escludi:
            continue
        if cercati & _iuv_del_fascicolo(fascicolo):
            usi.append({"id": fid, "titolo": str(getattr(fascicolo, "titolo", "") or ""),
                        "numero_rg": str(getattr(fascicolo, "numero_rg", "") or "")})
    return usi


def avviso_riuso(usi: list[dict[str, str]]) -> str:
    if not usi:
        return ""
    elenco = "; ".join(f"{u['titolo'] or u['id']}" + (f" (RG {u['numero_rg']})" if u["numero_rg"] else "") for u in usi[:5])
    return ("Attenzione: la stessa ricevuta telematica risulta già usata in un altro fascicolo dello studio "
            f"({elenco}). Una ricevuta prova un solo versamento: verifica prima di depositare.")


__all__ = ["avviso_riuso", "forme_iuv", "usi_altrove"]
