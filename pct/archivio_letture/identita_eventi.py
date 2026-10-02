"""Identità degli adempimenti condivisa dai lettori e dalle consegne.

Il giorno, da solo, non identifica un adempimento. La qualificazione usa
prima una prova esplicita del lettore, poi soltanto etichette riconoscibili.
Un termine generico non viene assimilato a un altro termine generico.
"""
from __future__ import annotations

import re
from typing import Any


def adempimento_da_testo(value: Any) -> str:
    text = " ".join(str(value or "").casefold().split())
    kinds = set()
    if re.search(r"notific\w*", text) and "ricorso" in text and "decreto" in text:
        kinds.add("notifica_ricorso_decreto")
    if "opposizione" in text:
        kinds.add("opposizione")
    if "note" in text and any(v in text for v in ("deposito", "sostituzione", "trattazione scritta", "difensive")):
        kinds.add("deposito_note")
    if "costituzione" in text:
        kinds.add("costituzione_resistente" if "resistente" in text else
                  "costituzione_convenuto" if "convenuto" in text else "costituzione")
    return next(iter(kinds)) if len(kinds) == 1 else ""


def adempimento_fatto(fatto: Any) -> str:
    codes = {
        str(p.get("dettaglio") or "")
        for p in (getattr(fatto, "prove", []) or [])
        if p.get("codice") == "istituto" and p.get("esito") == "ok" and p.get("dettaglio")
    }
    aliases = {"note_127_ter": "deposito_note"}
    if len(codes) == 1:
        code = next(iter(codes))
        return aliases.get(code, code)
    if len(codes) > 1:
        return ""
    return adempimento_da_testo(getattr(fatto, "etichetta", "")) or adempimento_da_testo(getattr(fatto, "contesto", ""))


def ambito_fatto(fatto: Any) -> str:
    """Evita che due termini diversi siano fusi per coincidenza della data."""
    if getattr(fatto, "categoria", "") != "data" or getattr(fatto, "campo", "") not in {"termine", "costituzione"}:
        return ""
    qualified = adempimento_fatto(fatto)
    if qualified:
        return qualified
    return "fonte:" + "|".join(str(getattr(fatto, k, "") or "") for k in ("tipo", "oggetto_id", "sha256", "id"))
