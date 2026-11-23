"""API v1 UI della prassi e dei testi della Giustizia amministrativa — /api/v1/ui/...

- ``GET /prassi?q=&ente=``: circolari e risoluzioni dell'Agenzia delle Entrate, circolari e messaggi dell'INPS che
  contengono le parole cercate (frasi fra virgolette), con data, numero, oggetto, brano e indirizzo ufficiale;
- ``GET /prassi/testo?id=``: il testo integrale di un documento;
- ``GET /giustizia-amministrativa/testi?q=``: sentenze del Consiglio di Stato e del CGA con il testo integrale.

Archivi scritti in sfondo (``scripts/prassi_recupero.py``, ``scripts/ga_testi_recupero.py``); qui si legge soltanto.
Dati pubblici, uguali per tutti gli studi: basta l'autenticazione.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from web.blueprints.api_v1_react import _richiedi_auth

api_v1_prassi = Blueprint("api_v1_prassi", __name__, url_prefix="/api/v1/ui")


def percorso(nome: str, variabile: str) -> Path:
    esplicito = str(current_app.config.get(variabile) or os.environ.get(variabile) or "").strip()
    if esplicito:
        return Path(esplicito)
    ancora = str(current_app.config.get("LEGAL_INTELLIGENCE_DB") or os.environ.get("PCT_LEGAL_INTELLIGENCE_DB")
                 or "./intelligence/motori.json")
    return Path(ancora).resolve().parent / nome


@api_v1_prassi.get("/prassi")
@_richiedi_auth
def prassi_cerca():
    from pct.prassi.archivio import ArchivioPrassi

    db = percorso("prassi.sqlite", "PCT_PRASSI_DB")
    if not db.is_file():
        return jsonify(ok=True, items=[], message="L'archivio della prassi non è ancora stato creato."), 200
    try:
        voci = ArchivioPrassi(db, sola_lettura=True).cerca(request.args.get("q", "")[:200], ente=request.args.get("ente", "")[:40],
                                                           limite=min(50, int(request.args.get("limite", 20) or 20)))
        return jsonify(ok=True, items=voci, archive=ArchivioPrassi(db, sola_lettura=True).conteggi())
    except Exception as exc:
        current_app.logger.exception("Prassi non disponibile: %s", exc)
        return jsonify(ok=False, items=[], message="La prassi non è consultabile in questo momento."), 200


@api_v1_prassi.get("/prassi/testo")
@_richiedi_auth
def prassi_testo():
    from pct.prassi.archivio import ArchivioPrassi

    db = percorso("prassi.sqlite", "PCT_PRASSI_DB")
    ident = request.args.get("id", "")[:120]
    testo = ArchivioPrassi(db, sola_lettura=True).testo(ident) if db.is_file() and ident else ""
    if not testo:
        return jsonify(ok=False, notFound=True, message="Documento non trovato nell'archivio della prassi."), 404
    return jsonify(ok=True, id=ident, text=testo)


@api_v1_prassi.get("/giustizia-amministrativa/testi")
@_richiedi_auth
def ga_testi_cerca():
    from pct.giustizia_amministrativa_testi import ArchivioTestiGA

    db = percorso("ga_testi.sqlite", "PCT_GA_TESTI_DB")
    if not db.is_file():
        return jsonify(ok=True, items=[], message="L'archivio dei testi della Giustizia amministrativa non è ancora stato creato."), 200
    try:
        return jsonify(ok=True, items=ArchivioTestiGA(db, sola_lettura=True).cerca(request.args.get("q", "")[:200]))
    except Exception as exc:
        current_app.logger.exception("Testi della Giustizia amministrativa non disponibili: %s", exc)
        return jsonify(ok=False, items=[], message="I testi non sono consultabili in questo momento."), 200


__all__ = ["api_v1_prassi"]
