"""La scheda della notifica da eseguire, come la legge l'avvocato nella lavorazione dell'impegno in agenda."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from pct.procedura_fasi.fonti import fonte

from .catalogo import _DEPOSITO_CIVILE, obbligo_per_codice
from .destinatari import come_notificare

_ORARIO_PEC = ("La notifica a mezzo PEC eseguita dopo le ore 21 si considera perfezionata alle ore 7 del giorno successivo: "
               "per l'ultimo giorno inviarla entro le 21.")


def _norme(identificativi: list[str]) -> list[dict[str, str]]:
    viste: list[dict[str, str]] = []
    for codice in dict.fromkeys(identificativi):
        voce = fonte(codice)
        if voce:
            viste.append({"id": codice, "norma": str(voce.get("norma") or ""), "url": str(voce.get("url") or "")})
    return viste


def scheda_notifica(codice: str, *, controparte: str = "", materia: str = "", fascicolo_id: str = "") -> dict[str, Any]:
    obbligo = obbligo_per_codice(codice)
    if obbligo.come:
        come = [{"testo": testo, "norme": list(norme)} for testo, norme in obbligo.come]
    else:
        come = come_notificare(controparte, materia=materia, impugnazione=obbligo.impugnazione)
    penale = materia == "penale" or "cpp_152" in obbligo.norme
    dopo = [obbligo.dopo] if obbligo.dopo else ([] if penale else [_DEPOSITO_CIVILE])
    avvertenze = [obbligo.nota] if obbligo.nota else []
    if not penale:
        avvertenze.append(_ORARIO_PEC)
    norme = list(obbligo.norme) + [str(n) for passo in come for n in passo["norme"]]
    if not penale:
        norme += ["cpc_147", "dispatt_196undecies"]
    prepara = {"section": "operazioni", "fase": "notifica", "ingresso": "fascicolo", "id_fascicolo": fascicolo_id}
    return {
        "atti": obbligo.atti,
        "destinatari": obbligo.destinatari if not controparte or obbligo.come else f"{obbligo.destinatari}: {controparte}",
        "aCuraDi": obbligo.a_cura_di,
        "come": [{"testo": str(passo["testo"]), "norme": [str(n) for n in passo["norme"]]} for passo in come],
        "avvertenze": avvertenze,
        "dopo": dopo,
        "norme": _norme(norme),
        "preparaHref": "/notifiche-legali?" + urlencode(prepara) if fascicolo_id else "",
    }


__all__ = ["scheda_notifica"]
