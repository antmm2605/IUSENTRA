"""Riferimenti normativi "vivi" per la libreria LegalSkills Italia.

Confronta i riferimenti dichiarati da voci del catalogo e passi dei
percorsi con gli aggiornamenti normativi pubblicati dalla pipeline
quotidiana (tabella ``normative`` del Legal Update Repository): quando
gli estremi di una norma citata coincidono con un aggiornamento
pubblicato, la voce viene proposta "da rivedere". Nessuna modifica
automatica al catalogo: la revisione resta dell'avvocato.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .library import LegalPromptLibrary, get_prompt_library
from .pathways import PathwayCatalog, get_pathway_catalog

_RX_NUMERO_ANNO = re.compile(r"\b(\d{1,4})\s*/\s*(\d{2,4})\b")
_RX_ANNO_N = re.compile(r"\b(\d{4})\s*,?\s*n\.\s*(\d{1,4})\b", re.IGNORECASE)


def estrai_estremi(testo: str) -> set[tuple[str, str]]:
    """Estrae coppie (numero, anno) da un riferimento normativo italiano.

    Riconosce "L. 604/1966", "D.Lgs. 28/2010", "Reg. UE 2016/679"
    (anno/numero) e "L. 8 marzo 2017, n. 24". Gli articoli di codice
    senza estremi di legge (es. "art. 641 c.p.c.") non producono coppie.
    """
    estremi: set[tuple[str, str]] = set()
    valore = str(testo or "")
    for a, b in _RX_NUMERO_ANNO.findall(valore):
        primo, secondo = int(a), int(b)
        if primo >= 1900 and secondo < primo:
            estremi.add((str(secondo), str(primo)))  # forma UE anno/numero
        elif secondo >= 1900:
            estremi.add((str(primo), str(secondo)))
        elif len(b) == 2:  # anno a due cifre (es. 392/78)
            anno = 1900 + secondo if secondo > 30 else 2000 + secondo
            estremi.add((str(primo), str(anno)))
    for anno, numero in _RX_ANNO_N.findall(valore):
        estremi.add((str(int(numero)), str(int(anno))))
    return estremi


def _estremi_aggiornamento(row: dict[str, Any]) -> set[tuple[str, str]]:
    numero = str(row.get("norm_number") or "").strip()
    anno = str(row.get("norm_year") or "").strip()
    estremi: set[tuple[str, str]] = set()
    if numero.isdigit() and anno.isdigit():
        estremi.add((str(int(numero)), str(int(anno))))
    estremi |= estrai_estremi(str(row.get("title") or ""))
    return estremi


def _aggiornamento_pubblico(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "titolo": str(row.get("title") or ""),
        "numero": str(row.get("norm_number") or ""),
        "anno": str(row.get("norm_year") or ""),
        "stato": str(row.get("status") or ""),
        "data": str(row.get("effective_date") or row.get("publication_date") or ""),
        "url": str(row.get("source_url") or ""),
    }


def revisioni_da_normative(
    rows: Iterable[dict[str, Any]],
    *,
    library: LegalPromptLibrary | None = None,
    pathway_catalog: PathwayCatalog | None = None,
) -> list[dict[str, Any]]:
    """Voci e passi da rivedere alla luce degli aggiornamenti pubblicati."""
    library = library or get_prompt_library()
    pathway_catalog = pathway_catalog or get_pathway_catalog()

    indice: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def _registra(chiavi: set[tuple[str, str]], voce: dict[str, Any]) -> None:
        for chiave in chiavi:
            indice.setdefault(chiave, []).append(voce)

    for area in library.aree():
        for voce in area.voci:
            for riferimento in voce.riferimenti:
                _registra(
                    estrai_estremi(riferimento),
                    {
                        "tipo": "voce",
                        "area_id": area.area_id,
                        "voce_id": voce.voce_id,
                        "nome": voce.nome,
                        "riferimento": riferimento,
                    },
                )
    for percorso in pathway_catalog.percorsi():
        for passo in percorso.passi:
            for riferimento in passo.riferimenti:
                _registra(
                    estrai_estremi(riferimento),
                    {
                        "tipo": "passo",
                        "percorso_id": percorso.percorso_id,
                        "passo_id": passo.passo_id,
                        "nome": f"{percorso.nome} — {passo.nome}",
                        "riferimento": riferimento,
                    },
                )

    revisioni: list[dict[str, Any]] = []
    visti: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for chiave in _estremi_aggiornamento(row):
            for voce in indice.get(chiave, []):
                identita = (
                    f"{voce['tipo']}:{voce.get('area_id', voce.get('percorso_id'))}:"
                    f"{voce.get('voce_id', voce.get('passo_id'))}:{chiave[0]}/{chiave[1]}"
                )
                if identita in visti:
                    continue
                visti.add(identita)
                revisioni.append({**voce, "aggiornamento": _aggiornamento_pubblico(row)})
    return revisioni


def voci_da_rivedere(revisioni: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    """Insieme (area_id, voce_id) delle voci del catalogo da rivedere."""
    return {
        (str(voce.get("area_id")), str(voce.get("voce_id")))
        for voce in revisioni or []
        if voce.get("tipo") == "voce"
    }


__all__ = ["estrai_estremi", "revisioni_da_normative", "voci_da_rivedere"]
