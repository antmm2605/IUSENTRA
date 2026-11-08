"""Corte costituzionale e giustizia amministrativa nella ricerca «Cerca norme e sentenze».

Le due fonti erano già nel software ma la ricerca non le consultava:
- pronunce e massime della Corte costituzionale, nell'archivio giurisprudenza dello studio (open data della Corte,
  https://dati.cortecostituzionale.it);
- decisioni di TAR e Consiglio di Stato dal catalogo OpenGA (open data della Giustizia amministrativa): solo
  estremi, oggetto ed esito; il testo si apre sul sito ufficiale.

Ogni fonte ha un tempo massimo breve: se non risponde la ricerca prosegue con le altre e lo dice.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

OPENGA_TIMEOUT = (2.0, 6.0)
_URL_OPENGA = "https://www.giustizia-amministrativa.it/dcsnprr"


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def pronunce_corte_costituzionale(domanda: str, *, limite: int = 6, corpus: Any | None = None) -> list[dict[str, Any]]:
    """Righe nel formato di ricerca (title, content, official_url...) dalle pronunce della Consulta."""
    if corpus is None:
        from web.helpers import get_giurisprudenza_corpus_readonly

        corpus = get_giurisprudenza_corpus_readonly()
    righe = corpus.cerca_sentenze(q=domanda, limit=limite, semantica=False, fonte_codice="corte_costituzionale")
    risultati = []
    for riga in righe:
        numero, anno = _testo(riga.get("numero_sentenza")), _testo(riga.get("anno_sentenza"))
        tipo = _testo(riga.get("tipo_provvedimento")).lower() or "pronuncia"
        massima = _testo(riga.get("massima_ufficiale") or riga.get("principio_sintetico") or riga.get("abstract"))
        risultati.append({
            "id": f"consulta:{riga.get('id')}",
            "title": f"Corte costituzionale, {tipo} n. {numero}/{anno}".strip() + (f" — {_testo(riga.get('oggetto'))[:160]}" if riga.get("oggetto") else ""),
            "content": massima or _testo(riga.get("titolo")),
            "official_url": _testo(riga.get("url_pagina_ufficiale") or riga.get("url_html_ufficiale")),
            "authority": "Corte costituzionale",
            "type": "giurisprudenza",
            "published_at": _testo(riga.get("data_deposito")),
            "is_official": True,
            "registro": f"{numero}/{anno}",
        })
    return risultati


def _richiesta_openga(endpoint: str, domanda: str) -> dict[str, Any]:
    import requests

    risposta = requests.post(endpoint.rstrip("/") + "/search", json={"q": domanda}, timeout=OPENGA_TIMEOUT, allow_redirects=False)
    risposta.raise_for_status()
    if len(risposta.content) > 2_000_000:
        raise ValueError("Risposta OpenGA troppo grande")
    return json.loads(risposta.content)


def decisioni_giustizia_amministrativa(domanda: str, *, limite: int = 6, endpoint: str | None = None,
                                       richiesta: Callable[[str, str], dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Decisioni TAR e Consiglio di Stato (solo estremi, oggetto ed esito) dal catalogo OpenGA locale."""
    endpoint = endpoint if endpoint is not None else os.getenv("IUSENTRA_OPENGA_SEARCH_URL", "").strip()
    if not endpoint:
        return []
    dati = (richiesta or _richiesta_openga)(endpoint, domanda)
    if not isinstance(dati, dict) or dati.get("evidence_scope") != "metadata_only":
        return []
    risultati = []
    for riga in (dati.get("risultati") or [])[:limite]:
        if not isinstance(riga, dict):
            continue
        organo, numero = _testo(riga.get("organo_giudicante")), _testo(riga.get("numero_sentenza"))
        anno, oggetto, esito = _testo(riga.get("anno_sentenza")), _testo(riga.get("oggetto")), _testo(riga.get("esito"))
        numero_breve = numero[-5:].lstrip("0") if len(numero) == 9 and numero.startswith(anno) else numero
        risultati.append({
            "id": f"openga:{riga.get('decisione_id') or riga.get('resource_id')}",
            "title": f"{organo}, sentenza n. {numero_breve}/{anno}" + (f" — {oggetto.capitalize()}" if oggetto else ""),
            "content": " · ".join(x for x in (f"Oggetto: {oggetto.capitalize()}" if oggetto else "",
                                                 f"Esito: {esito.capitalize()}" if esito else "",
                                                 f"Ricorso n. {riga.get('numero_ricorso')}" if riga.get("numero_ricorso") else "") if x),
            "official_url": _testo(riga.get("official_search_url")) or _URL_OPENGA,
            "authority": "Giustizia amministrativa — OpenGA",
            "type": "giurisprudenza",
            "published_at": anno,
            "is_official": True,
            "registro": f"{numero_breve}/{anno}",
        })
    return risultati


__all__ = ["decisioni_giustizia_amministrativa", "pronunce_corte_costituzionale"]
