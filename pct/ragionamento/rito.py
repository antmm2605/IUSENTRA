"""Il rito della causa: dal codice oggetto ministeriale PST, confermato dagli atti catalogati.

Fonte primaria: il catalogo ufficiale dei codici oggetto (`pct/data/cataloghi/codici_oggetto_pst.json`,
XSD del PST): l'area e il codice padre dicono se la pratica è cognizione ordinaria, lavoro, monitorio,
esecuzione o volontaria giurisdizione. Se il codice manca, decidono gli atti del catalogo (ricorso per
decreto ingiuntivo, atto di pignoramento, ricorso ex art. 414 c.p.c.). La sospensione feriale dei termini
non si applica alle controversie di lavoro (art. 3 L. 742/1969).
"""

from __future__ import annotations

import importlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from .modello import Rito
from .testo import pulito, semplice

_CATALOGO = Path(importlib.import_module("pct").__file__).resolve().parent / "data" / "cataloghi" / "codici_oggetto_pst.json"
ETICHETTE = {
    "cognizione": "cognizione ordinaria",
    "lavoro": "rito del lavoro",
    "monitorio": "procedimento monitorio (decreto ingiuntivo)",
    "esecuzione_mobiliare": "espropriazione mobiliare",
    "esecuzione_presso_terzi": "espropriazione presso terzi",
    "esecuzione_immobiliare": "espropriazione immobiliare",
    "volontaria_giurisdizione": "volontaria giurisdizione",
    "sommario": "procedimento speciale sommario",
    "ignoto": "rito non determinato",
}
# Parole della denominazione dell'ente che fanno della controparte una pubblica amministrazione.
_PA = ("ministero", "mim", "miur", "avvocatura", "inps", "inail", "agenzia delle entrate", "comune di", "regione",
       "azienda sanitaria", "asp ", "asl ", "presidenza del consiglio", "universita", "prefettura", "questura")


@lru_cache(maxsize=1)
def _codici() -> dict[str, dict[str, Any]]:
    try:
        dati = json.loads(_CATALOGO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(r.get("codice")): r for r in dati.get("records") or []}


def rito_da_codice(codice: str) -> tuple[str, dict[str, Any]]:
    voce = _codici().get(pulito(codice)[:6])
    if not voce:
        return "", {}
    area, padre, descrizione = semplice(voce.get("area")), pulito(voce.get("codicePadre")), semplice(voce.get("descrizione"))
    if area.startswith("esecuzioni immobiliari"):
        return "esecuzione_immobiliare", voce
    if area.startswith("esecuzioni mobiliari"):
        return ("esecuzione_presso_terzi" if "presso terzi" in descrizione else "esecuzione_mobiliare"), voce
    if area.startswith("volontaria giurisdizione"):
        return "volontaria_giurisdizione", voce
    if area.startswith("lavoro"):
        return "lavoro", voce
    if padre == "010" or "ingiuntivo" in descrizione:
        return "monitorio", voce
    if area.startswith("procedimenti speciali sommari"):
        return "sommario", voce
    if area.startswith("contenzioso civile"):
        return "cognizione", voce
    return "", voce


def rito_da_atti(etichette: Iterable[str]) -> str:
    """Il rito che gli atti catalogati dimostrano da soli, o stringa vuota."""
    testi = [semplice(e) for e in etichette]
    if any("pignoramento" in t for t in testi):
        return "esecuzione_presso_terzi" if any("presso terzi" in t for t in testi) else "esecuzione_mobiliare"
    if any("decreto ingiuntivo" in t for t in testi):
        return "monitorio"
    if any("414 c.p.c" in t or "materia di lavoro" in t for t in testi):
        return "lavoro"
    return ""


def contro_pa(*nomi: object) -> bool:
    testo = " " + " ".join(semplice(n) for n in nomi) + " "
    return any(f" {p.strip()}" in testo or p in testo for p in _PA)


def determina_rito(fascicolo: dict[str, Any], etichette_atti: Iterable[str]) -> Rito:
    codice = pulito(fascicolo.get("codice_oggetto_pst")) or pulito(fascicolo.get("oggetto"))[:6]
    dal_codice, voce = rito_da_codice(codice)
    dagli_atti = rito_da_atti(etichette_atti)
    if dal_codice:
        scelto, fonte = dal_codice, f"codice oggetto PST {voce.get('codice')} – {voce.get('descrizione')} (area «{voce.get('area')}»)"
    elif dagli_atti:
        scelto, fonte = dagli_atti, "atti catalogati del fascicolo (codice oggetto PST assente)"
    elif semplice(fascicolo.get("tipo")).endswith("lavoro"):
        scelto, fonte = "lavoro", "tipo del fascicolo (codice oggetto PST assente)"
    else:
        scelto, fonte = "ignoto", "nessun codice oggetto PST e nessun atto che dica il rito"
    pa = contro_pa(fascicolo.get("controparte"), fascicolo.get("titolo"), fascicolo.get("avvocato_controparte"))
    return Rito(
        codice=scelto, etichetta=ETICHETTE.get(scelto, scelto), fonte=fonte,
        codice_oggetto=pulito(voce.get("codice")), area=pulito(voce.get("area")),
        padre=pulito(voce.get("descrizionePadre") or voce.get("codicePadre")),
        sospensione_feriale=scelto != "lavoro", contro_pa=pa,
    )


__all__ = ["ETICHETTE", "contro_pa", "determina_rito", "rito_da_atti", "rito_da_codice"]
