"""Di che cosa tratta la pratica: dall'oggetto dichiarato e dagli atti principali.

L'oggetto lo dice il fascicolo; il *petitum* lo dicono gli atti. Quando il testo
dell'atto principale è indicizzato, la lettura ne estrae la domanda — la frase
che segue «chiede», «conclude», «voglia» — e la cita testualmente: è la prova
di che cosa si è chiesto al giudice, non un riassunto inventato.
"""

from __future__ import annotations

import re
from typing import Any

from ._testo import pulisci

_FORMULE_DOMANDA = re.compile(
    r"\b(?:chiede|chiedono|chiedendo|conclude|concludono|voglia|vogliano|si\s+chiede|ingiunge|intima)\b",
    re.IGNORECASE,
)
_NATURE_PRINCIPALI = {"atto_principale", "atto_difensivo", "atto_esecutivo"}
LUNGHEZZA_MASSIMA_PETITUM = 420


def _testo_documento(documento: dict[str, Any]) -> str:
    return pulisci(documento.get("lex_text_excerpt") or documento.get("testo") or documento.get("text"))


def petitum(testo: str) -> str:
    """La domanda dell'atto, citata dal testo a partire dalla formula che la apre."""
    pulito = pulisci(testo)
    if not pulito:
        return ""
    corrispondenza = _FORMULE_DOMANDA.search(pulito)
    if not corrispondenza:
        return ""
    frase = pulito[corrispondenza.start():]
    # Si ferma al primo punto fermo seguito da maiuscola, per non trascinare
    # dietro dichiarazioni di valore o firme.
    taglio = re.search(r"\.\s+(?=[A-ZÀÈÉÌÒÙ])", frase)
    if taglio:
        frase = frase[: taglio.start() + 1]
    frase = frase.strip()
    if len(frase) > LUNGHEZZA_MASSIMA_PETITUM:
        frase = frase[:LUNGHEZZA_MASSIMA_PETITUM].rsplit(" ", 1)[0] + "…"
    return frase


def oggetto(fascicolo: dict[str, Any], documenti: list[dict[str, Any]], catalogo: list[dict[str, Any]]) -> dict[str, Any]:
    per_documento = {pulisci(voce.get("document_id")): voce for voce in catalogo}
    principali: list[dict[str, Any]] = []
    for documento in documenti:
        voce = per_documento.get(pulisci(documento.get("id")))
        natura = pulisci((voce or {}).get("document_nature"))
        etichetta = pulisci((voce or {}).get("document_label"))
        tipo = pulisci(documento.get("tipo")).upper()
        if natura in _NATURE_PRINCIPALI or (not voce and tipo in {"RICORSO", "CITAZIONE", "COMPARSA", "MEMORIA"}):
            principali.append({
                "id": pulisci(documento.get("id")),
                "nome": pulisci(documento.get("nome")),
                "etichetta": etichetta or tipo.title(),
                "data": pulisci(documento.get("data_documento") or documento.get("data_caricamento"))[:10],
                "petitum": pulisci(documento.get("domanda_archivio")),
                "content_sha256": pulisci(documento.get("content_sha256")),
            })
    visti: set[str] = set()
    unici = []
    for voce in principali:
        chiave = voce["content_sha256"] or voce["id"]
        if chiave not in visti:
            visti.add(chiave)
            unici.append(voce)
    principali = unici
    principali.sort(key=lambda voce: voce["data"])
    con_domanda = [voce for voce in principali if voce["petitum"]]
    return {
        "oggetto_dichiarato": pulisci(fascicolo.get("oggetto")),
        "atti_principali": principali[:6],
        "domanda": con_domanda[0] if con_domanda else None,
    }


__all__ = ["LUNGHEZZA_MASSIMA_PETITUM", "oggetto", "petitum"]
