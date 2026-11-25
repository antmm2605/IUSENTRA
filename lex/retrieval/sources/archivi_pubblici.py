"""Adattatori del retrieval per la prassi (AdE, INPS), la Gazzetta Ufficiale e i testi della giustizia amministrativa."""

from __future__ import annotations

import logging

from lex.retrieval.archivi_pubblici import cerca_gazzetta, cerca_prassi, cerca_testi_ga

from . import row_to_evidence

_log = logging.getLogger(__name__)


def _testo(queries, request) -> str:
    return str((queries[0] if queries else "") or getattr(request, "query", "") or "")


def _ente(testo: str) -> str:
    t = testo.lower()
    if "inps" in t:
        return "inps"
    if "agenzia delle entrate" in t or "agenzia entrate" in t:
        return "agenzia_entrate"
    return ""


class PrassiSource:
    source_name = "prassi"

    def search(self, queries, request, context):
        testo = _testo(queries, request)
        try:
            righe = cerca_prassi(testo, ente=_ente(str(getattr(request, "query", "") or testo)))
        except Exception:
            _log.exception("archivio della prassi non consultabile")
            return []
        return [row_to_evidence({
            "type": "prassi", "id": r.get("id"), "score": 0.7,
            "title": f"{r.get('ente', '')} — {r.get('tipo', '')} n. {r.get('numero', '')} del {r.get('data', '')}".strip(" —"),
            "excerpt": " ".join(str(x) for x in (r.get("oggetto"), r.get("brano")) if x),
            "authority": r.get("ente", ""), "official_url": r.get("url", ""), "published_at": r.get("data", ""),
            "verified_reference": True,
        }, "prassi") for r in righe]


class GazzettaSource:
    source_name = "gazzetta"

    def search(self, queries, request, context):
        try:
            righe = cerca_gazzetta(_testo(queries, request))
        except Exception:
            _log.exception("archivio della Gazzetta Ufficiale non consultabile")
            return []
        return [row_to_evidence({
            "type": "normativa", "id": r.get("id"), "score": 0.65,
            "title": " ".join(str(x) for x in (r.get("tipo"), r.get("numero_atto") and f"n. {r.get('numero_atto')}",
                                                r.get("data_atto") and f"del {r.get('data_atto')}") if x) or "Atto in Gazzetta",
            "excerpt": " ".join(str(x) for x in (r.get("descrizione"), r.get("emittente"),
                                                  f"G.U. {r.get('serie', '')} n. {r.get('numero_gu', '')} del {r.get('data_gu', '')}") if x),
            "authority": "Gazzetta Ufficiale della Repubblica italiana", "official_url": r.get("url", ""),
            "published_at": r.get("data_gu", ""),
        }, "normativa") for r in righe]


class GiustiziaAmministrativaSource:
    source_name = "giustizia_amministrativa"

    def search(self, queries, request, context):
        try:
            righe = cerca_testi_ga(str(getattr(request, "query", "") or _testo(queries, request)))
        except Exception:
            _log.exception("archivio dei testi della giustizia amministrativa non consultabile")
            return []
        return [row_to_evidence({
            "type": "giurisprudenza", "id": r.get("id"), "score": 0.7,
            "title": f"{r.get('nome_sede', '')} — {r.get('tipo', '')} n. {str(r.get('numero', ''))[-5:].lstrip('0')}/{r.get('anno', '')}",
            "excerpt": " ".join(str(x) for x in (r.get("oggetto"), r.get("brano")) if x),
            "authority": r.get("nome_sede", ""), "official_url": r.get("url", ""),
            "published_at": r.get("pubblicato_il", ""), "verified_reference": True,
        }, "giurisprudenza") for r in righe]
