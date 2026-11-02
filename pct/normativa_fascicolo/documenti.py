"""Gruppo (c): le norme dei tipi di documento presenti nel fascicolo.

Il tipo di ogni documento è quello già registrato dal catalogo dal contenuto
(assegnazioni SQL di `pct.document_intelligence`): qui non si legge alcun
documento. Dal tipo si risale alla norma che lo definisce con le regole
d'identità dal titolo (`pct.document_intelligence.titoli`, campo `fonte`) e con
le fonti per natura del catalogo (`document_source_ids`).
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from typing import Any

from pct.document_intelligence.catalog_sources import document_source_ids

from .voci import aggiungi, voce_catalogo

_FONTI_GENERICHE = {"catalog_agid_metadati"}
# Le assegnazioni da rivedere, superate o respinte non dicono il tipo del documento.
_STATI_VALIDI = {"proposed", "confirmed", "catalogued"}


@lru_cache(maxsize=1)
def _indici() -> tuple[dict[str, str], dict[str, str]]:
    """Etichetta → fonte e natura → fonte, solo quando la corrispondenza è univoca."""
    from pct.document_intelligence.titoli import REGOLE_TITOLO

    per_etichetta: dict[str, set[str]] = defaultdict(set)
    per_natura: dict[str, set[str]] = defaultdict(set)
    for regola in REGOLE_TITOLO:
        if regola.fonte:
            per_etichetta[regola.label.strip().lower()].add(regola.fonte)
            per_natura[regola.role].add(regola.fonte)
    univoche = lambda indice: {k: next(iter(v)) for k, v in indice.items() if len(v) == 1}  # noqa: E731
    return univoche(per_etichetta), univoche(per_natura)


def _valore(riga: Any, campo: str) -> str:
    valore = riga.get(campo, "") if isinstance(riga, dict) else getattr(riga, campo, "")
    return " ".join(str(valore or "").split())


def fonti_del_tipo(etichetta: str, natura: str, sezione: str, profilo: str = "") -> list[str]:
    per_etichetta, per_natura = _indici()
    fonti: list[str] = []
    for candidata in (per_etichetta.get(etichetta.strip().lower()), per_natura.get(natura)):
        if candidata and candidata not in fonti:
            fonti.append(candidata)
    for candidata in document_source_ids(natura, sezione, profilo or None):
        if candidata not in _FONTI_GENERICHE and candidata not in fonti:
            fonti.append(candidata)
    return fonti


def norme_documenti(catalogo: list[Any], nomi: dict[str, str], totale_documenti: int) -> dict[str, Any]:
    """`catalogo`: assegnazioni del catalogo (dict o oggetti); `nomi`: id documento → nome visibile."""
    voci: dict[str, dict[str, Any]] = {}
    documenti_per_voce: dict[str, list[str]] = defaultdict(list)
    tipo_per_voce: dict[str, str] = {}
    catalogati = 0
    for riga in catalogo:
        if _valore(riga, "status").lower() not in _STATI_VALIDI:
            continue
        catalogati += 1
        etichetta = _valore(riga, "document_label")
        documento = nomi.get(_valore(riga, "document_id")) or etichetta or "documento"
        for identificativo in fonti_del_tipo(etichetta, _valore(riga, "document_nature"),
                                             _valore(riga, "document_section"), _valore(riga, "profile_id")):
            voce = voce_catalogo(identificativo)
            # Un codice intero non dice quale norma regola il documento: serve l'articolo.
            if voce is None or not voce.get("url") or "art" not in voce["norma"].lower():
                continue
            aggiungi(voci, voce, "")
            if documento not in documenti_per_voce[voce["id"]]:
                documenti_per_voce[voce["id"]].append(documento)
            tipo_per_voce.setdefault(voce["id"], etichetta)
    for chiave, voce in voci.items():
        nomi_doc = documenti_per_voce[chiave]
        tipo = tipo_per_voce.get(chiave) or "documento"
        if len(nomi_doc) == 1:
            voce["perche"] = [f"perché: documento «{nomi_doc[0]}» nel fascicolo ({tipo})"]
        else:
            elenco = ", ".join(f"«{n}»" for n in nomi_doc[:3]) + (f" e altri {len(nomi_doc) - 3}" if len(nomi_doc) > 3 else "")
            voce["perche"] = [f"perché: {len(nomi_doc)} documenti nel fascicolo ({tipo}): {elenco}"]
    if voci:
        vuoto = ""
    elif not totale_documenti:
        vuoto = "Nessun documento nel fascicolo."
    elif not catalogati:
        vuoto = "I documenti non sono ancora catalogati: la norma di ciascun tipo comparirà dopo la catalogazione."
    else:
        vuoto = "I tipi di documento catalogati non hanno una norma propria nel catalogo."
    return {"voci": list(voci.values()), "catalogati": catalogati, "documenti": totale_documenti, "vuoto": vuoto}


__all__ = ["fonti_del_tipo", "norme_documenti"]
