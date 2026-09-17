"""Le lacune della conoscenza procedurale: ciò che il fascicolo cita e le schede non coprono ancora.

Un rito senza scheda, un canale sconosciuto, una norma citata da una scadenza o
da una PEC e assente dal registro delle fonti: il software non inventa, ma non
tace. Le lacune vengono dichiarate nella lettura, con la chiave esatta da
cercare, così che il presidio normativo (aggiornamenti legali, ricerca
pubblica governata di Lex) possa colmarle con fonti ufficiali.
"""

from __future__ import annotations

import re
from typing import Any

from .depositi import canale_deposito
from .fonti import FONTI
from .riti import rito_per_fascicolo

_RIFERIMENTO_NORMATIVO = re.compile(
    r"\b(?:artt?\.?\s*\d+[\w-]*(?:\s*(?:e|,)\s*\d+[\w-]*)*\s*(?:c\.p\.c\.|c\.p\.p\.|c\.p\.a\.|c\.c\.|disp\.\s*att\.\s*c\.p\.c\.|d\.?lgs\.?\s*\d+/\d{4}|l\.\s*\d+/\d{4}|d\.?m\.?\s*\d+/\d{4}|d\.?p\.?r\.?\s*\d+/\d{4}|d\.?l\.?\s*\d+/\d{4}))",
    re.IGNORECASE,
)


def _norme_registrate() -> set[str]:
    return {_chiave(voce["norma"]) for voce in FONTI.values()}


def _chiave(testo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(testo or "").lower().replace("artt.", "art.").replace("articolo", "art."))


def riferimenti_nel_testo(testo: str) -> list[str]:
    """I riferimenti normativi scritti in un testo («art. 171-ter c.p.c.», «D.Lgs. 28/2010»)."""
    return [" ".join(m.group(0).split()) for m in _RIFERIMENTO_NORMATIVO.finditer(str(testo or ""))]


def lacune_conoscenza(
    *,
    tipo: str = "",
    tipo_procedimento: str = "",
    canale_operativo: str = "",
    riferimenti: list[str] | tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Le lacune: rito o canale senza scheda, norme citate e non registrate."""
    lacune: list[dict[str, Any]] = []
    rito = rito_per_fascicolo(tipo, tipo_procedimento)
    if not rito and (tipo or tipo_procedimento):
        chiave = " ".join(str(tipo_procedimento or tipo).split())
        lacune.append({
            "tipo": "rito",
            "chiave": chiave,
            "descrizione": f"Il rito «{chiave}» non ha ancora una scheda di fasi e termini: va predisposta dalle fonti ufficiali prima di indicare adempimenti.",
        })
    canale = " ".join(str(canale_operativo or "").split())
    if canale and not canale_deposito(canale):
        lacune.append({
            "tipo": "canale",
            "chiave": canale,
            "descrizione": f"Il canale di deposito «{canale}» non ha una scheda: fasi, ricevute e termini vanno verificati sulle specifiche del portale.",
        })
    registrate = _norme_registrate()
    viste: set[str] = set()
    for riferimento in riferimenti:
        for norma in riferimenti_nel_testo(riferimento):
            chiave = _chiave(norma)
            if not chiave or chiave in viste:
                continue
            viste.add(chiave)
            if chiave in registrate:
                continue
            lacune.append({
                "tipo": "norma",
                "chiave": norma,
                "descrizione": f"La norma «{norma}» è citata nel fascicolo ma non è nel registro delle fonti verificate: il testo vigente va acquisito da Normattiva prima di fondarvi un termine.",
            })
    return lacune


__all__ = ["lacune_conoscenza", "riferimenti_nel_testo"]
