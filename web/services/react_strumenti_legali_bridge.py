"""Payload React della suite Strumenti Forensi.

Espone il catalogo degli strumenti già dichiarato dal dominio e, per quelli che
hanno un contratto di input in ``pct.calcolatori.schema``, i campi con cui la
shell React costruisce il modulo. Gli strumenti non ancora dichiarati restano
raggiungibili nella vista classica: la pagina li elenca comunque con il proprio
collegamento, così la migrazione non toglie funzioni all'utente.

Il calcolo non è duplicato qui: passa dai metodi di ``GestioneStrumentiLegali``
già usati dalla vista classica e dagli endpoint JSON esistenti.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori.schema import schema_calcolatore


def build_react_strumenti_legali_payload(
    *,
    catalogo: List[Mapping[str, Any]],
    form_state: Mapping[str, str],
    tool_richiesto: str = "",
) -> Dict[str, Any]:
    """Catalogo, schema dei moduli e valori iniziali per la pagina React."""

    strumenti: List[Dict[str, Any]] = []
    for voce in catalogo:
        tool_id = str(voce.get("id") or "").strip()
        if not tool_id:
            continue
        schema = schema_calcolatore(tool_id)
        campi = list(schema.get("campi", [])) if schema else []
        strumenti.append(
            {
                "id": tool_id,
                "title": str(voce.get("title") or ""),
                "subtitle": str(voce.get("subtitle") or ""),
                "categoria": str(voce.get("categoria") or "Altro"),
                "icon": str(voce.get("icon") or ""),
                "reso_in_react": bool(campi),
                "azione": str(schema.get("azione") or "Calcola") if schema else "",
                "campi": [
                    {**campo, "value": str(form_state.get(campo["name"], "") or "")}
                    for campo in campi
                ],
                "href_vista_classica": f"/strumenti-legali/?tool={tool_id}&_legacy=1",
            }
        )

    categorie = sorted({voce["categoria"] for voce in strumenti})
    attivo = str(tool_richiesto or "").strip()
    if attivo not in {voce["id"] for voce in strumenti}:
        attivo = next((voce["id"] for voce in strumenti if voce["reso_in_react"]), "")

    return {
        "strumenti": strumenti,
        "categorie": categorie,
        "tool_attivo": attivo,
        "totale": len(strumenti),
        "totale_in_react": sum(1 for voce in strumenti if voce["reso_in_react"]),
        "endpoint_calcolo": "/api/v1/ui/strumenti-legali/calcola",
    }
