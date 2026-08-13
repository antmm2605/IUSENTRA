"""Payload React della suite Strumenti Forensi.

Espone il catalogo degli strumenti già dichiarato dal dominio e, per quelli che
hanno un contratto di input in ``pct.calcolatori.schema``, i campi con cui la
shell React costruisce il modulo.

Il calcolo non è duplicato qui: passa dai metodi di ``GestioneStrumentiLegali``
già usati dagli endpoint JSON esistenti.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from pct.calcolatori.schema import schema_calcolatore


def sorgenti_opzioni(gestore: Any) -> Dict[str, List[Dict[str, str]]]:
    """Cataloghi di opzioni già esposti dal dominio, indicizzati per nome.

    Gli schemi dichiarano ``options_from`` invece di congelare gli elenchi:
    materie e gradi del D.M. 55/2014 e categorie del contributo unificato
    restano una fonte sola, quella del gestore.
    """

    onorari = gestore.opzioni_onorari_forensi()
    return {
        "onorari_materie": list(onorari.get("materie", [])),
        "onorari_gradi": list(onorari.get("gradi", [])),
        "onorari_complessita": list(onorari.get("complessita", [])),
        "onorari_fasi": list(onorari.get("fasi", [])),
        "contributo_unificato_categorie": list(gestore.opzioni_contributo_unificato()),
        "contributo_unificato_valore": list(gestore.opzioni_valore_contributo_unificato()),
        "termini_processuali_modelli": list(gestore.opzioni_termini_processuali()),
    }


def _normalizza_opzioni(voci: Iterable[Mapping[str, Any]]) -> List[Dict[str, str]]:
    normalizzate: List[Dict[str, str]] = []
    for voce in voci:
        valore = str(voce.get("value", "") or "")
        if not valore:
            continue
        normalizzate.append({"value": valore, "label": str(voce.get("label", "") or valore)})
    return normalizzate


def _campo_risolto(
    campo: Mapping[str, Any],
    form_state: Mapping[str, str],
    opzioni: Mapping[str, List[Dict[str, str]]],
) -> Dict[str, Any]:
    risolto = {chiave: valore for chiave, valore in campo.items() if chiave != "options_from"}
    sorgente = str(campo.get("options_from") or "")
    if sorgente:
        risolto["options"] = _normalizza_opzioni(opzioni.get(sorgente, []))
    risolto["value"] = str(form_state.get(str(campo["name"]), "") or "")
    return risolto


def build_react_strumenti_legali_payload(
    *,
    catalogo: List[Mapping[str, Any]],
    form_state: Mapping[str, str],
    tool_richiesto: str = "",
    opzioni: Mapping[str, List[Dict[str, str]]] | None = None,
) -> Dict[str, Any]:
    """Catalogo, schema dei moduli e valori iniziali per la pagina React."""

    cataloghi_opzioni = dict(opzioni or {})
    strumenti: List[Dict[str, Any]] = []
    for voce in catalogo:
        tool_id = str(voce.get("id") or "").strip()
        if not tool_id:
            continue
        schema = schema_calcolatore(tool_id)
        campi = list(schema.get("campi", [])) if schema else []
        # Un campo a opzioni dinamiche senza sorgente risolta lascerebbe una
        # select vuota: in quel caso lo strumento resta sulla vista classica.
        risolvibile = all(
            not campo.get("options_from") or cataloghi_opzioni.get(str(campo["options_from"]))
            for campo in campi
        )
        strumenti.append(
            {
                "id": tool_id,
                "title": str(voce.get("title") or ""),
                "subtitle": str(voce.get("subtitle") or ""),
                "categoria": str(voce.get("categoria") or "Altro"),
                "icon": str(voce.get("icon") or ""),
                "reso_in_react": bool(campi) and risolvibile,
                "azione": str(schema.get("azione") or "Calcola") if schema else "",
                "campi": [
                    _campo_risolto(campo, form_state, cataloghi_opzioni)
                    for campo in campi
                ]
                if risolvibile
                else [],
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
