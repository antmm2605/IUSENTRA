"""La pagina /pat: i fascicoli amministrativi con lo stato del deposito Formweb.

Per ogni fascicolo amministrativo aperto: sede e tipo di ricorso come li
chiede il Portale dell'Avvocato, dati ancora da indicare per la bozza, ultimo
deposito registrato e il collegamento alla sezione del fascicolo dove si
prepara. Legge solo i dati salvati: nessun documento viene riaperto.
"""

from __future__ import annotations

from typing import Any

from flask import current_app

from pct.fascicoli import TipoFascicolo
from pct.pat_formweb import catalogo
from web.services import pat_formweb_contesto as contesto


def _riga(fascicolo: Any, salvato: dict[str, Any]) -> dict[str, Any]:
    proc = salvato.get("procedimento") or {}
    sede = proc.get("sede") or contesto.sede_da_ufficio(fascicolo.tribunale)
    nrg = proc.get("nrg") or contesto.nrg(fascicolo)
    tipo = catalogo.descrizione("tipoRicorsoCds" if catalogo.ambito(sede) in {"CDS", "CGARS"} else "tipoRicorsoTar",
                                str(proc.get("tipoRicorso") or ""))
    mancanti = [voce for voce, valore in (("sede", sede), ("tipo di ricorso", tipo), ("contributo", proc.get("cuTipologia")))
                if not valore]
    ultimo = (salvato.get("depositi") or [None])[0]
    return {
        "id": fascicolo.id, "titolo": fascicolo.titolo, "numero": fascicolo.numero, "cliente": fascicolo.nome_cliente,
        "sede": next((e for c, e in catalogo.SEDI.values() if c == sede), fascicolo.tribunale or ""),
        "nrg": nrg, "tipoRicorso": tipo, "mancanti": mancanti,
        "ultimoDeposito": {"tipo": ultimo["tipo"], "stato": ultimo["stato"], "quando": ultimo["aggiornatoIl"]} if ultimo else None,
        "link": f"/fascicoli/{fascicolo.id}#pat-formweb",
    }


def panoramica() -> dict[str, Any]:
    try:
        fascicoli = current_app.extensions["core_runtime"]["get_fascicoli"]().tutti(tipo=TipoFascicolo.AMMINISTRATIVO)
    except Exception:
        current_app.logger.warning("Fascicoli amministrativi non leggibili per la pagina PAT", exc_info=True)
        fascicoli = []
    archivio = contesto.archivio()
    righe = [_riga(f, archivio.fascicolo(f.id)) for f in fascicoli]
    stati = [r["ultimoDeposito"]["stato"] for r in righe if r["ultimoDeposito"]]
    return {
        "ok": True,
        "fascicoli": righe,
        "totali": {"fascicoli": len(righe), "daCompletare": sum(1 for r in righe if r["mancanti"]),
                   "inviati": stati.count("inviato"), "depositati": stati.count("depositato"),
                   "rifiutati": stati.count("rifiutato")},
        "depositi": [{"id": d["id"], "nome": d["nome"], "link": catalogo.link_deposito(d["id"])} for d in catalogo.DEPOSITI],
        "linkPortale": catalogo.PORTALE,
        "fonte": catalogo.FONTE,
    }


__all__ = ["panoramica"]
