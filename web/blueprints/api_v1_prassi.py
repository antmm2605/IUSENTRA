"""API v1 UI della prassi e dei testi della Giustizia amministrativa — /api/v1/ui/...

- ``GET /prassi?q=&ente=``: circolari e risoluzioni dell'Agenzia delle Entrate, circolari e messaggi dell'INPS che
  contengono le parole cercate (frasi fra virgolette), con data, numero, oggetto, brano e indirizzo ufficiale;
- ``GET /prassi/testo?id=``: il testo integrale di un documento;
- ``GET /giustizia-amministrativa/testi?q=``: sentenze del Consiglio di Stato, del CGA e dei TAR con il testo integrale;
- ``GET /giustizia-amministrativa/testo?organo=&anno=&numero=&ricorso=`` (``/testo/pagina`` per la pagina da leggere):
  il testo di una sentenza chiesta ora; se l'archivio non lo ha, si scarica subito dal sito ufficiale (al più 15
  secondi), si salva nell'archivio e, se non è disponibile, lo si dice chiaramente.

Archivi scritti dai lavori pianificati orari dell'app (``pct/fonti_in_sfondo.py``), unico scrittore; la lettura su
richiesta aggiunge soltanto la sentenza chiesta, se è nel catalogo OpenGA o se il testo ufficiale ne riporta gli estremi.
Dati pubblici, uguali per tutti gli studi: basta l'autenticazione.
"""
from __future__ import annotations

import html
import os
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request

from web.blueprints.api_v1_react import _richiedi_auth

api_v1_prassi = Blueprint("api_v1_prassi", __name__, url_prefix="/api/v1/ui")


def percorso(nome: str, variabile: str) -> Path:
    from pct.fonti_in_sfondo import percorso_ga, percorso_prassi

    config = {**os.environ, **current_app.config}
    return percorso_ga(config) if nome == "ga_testi.sqlite" else percorso_prassi(config)


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


def _testo_su_richiesta() -> dict:
    from pct.giustizia_amministrativa_testi import ArchivioTestiGA, testo_su_richiesta

    a = request.args
    if not str(a.get("anno", "")).strip().isdigit() or not str(a.get("numero", "")).strip():
        return {"ok": False, "testo": "", "url": "", "messaggio": "Indica numero e anno della sentenza."}
    try:
        archivio = ArchivioTestiGA(percorso("ga_testi.sqlite", "PCT_GA_TESTI_DB"))
        from pct.fonti_in_sfondo import catalogo_openga

        # L'app è l'unico scrittore dell'archivio (lo stesso del lavoro pianificato orario).
        return testo_su_richiesta(archivio, anno=a.get("anno", "")[:4], numero=a.get("numero", "")[:12],
                                  organo=a.get("organo", "")[:120], sede=a.get("sede", "")[:3],
                                  ricorso=a.get("ricorso", "")[:12],
                                  catalogo=catalogo_openga({**os.environ, **current_app.config}))
    except Exception:
        current_app.logger.exception("Lettura su richiesta non riuscita")
        return {"ok": False, "testo": "", "url": "", "messaggio": "Lettura non riuscita: riprova fra poco o apri il sito ufficiale."}


@api_v1_prassi.get("/giustizia-amministrativa/testo")
@_richiedi_auth
def ga_testo():
    esito = _testo_su_richiesta()
    return jsonify(ok=bool(esito.get("ok")), text=esito.get("testo", ""), url=esito.get("url", ""), source=esito.get("fonte", ""),
                   publishedAt=esito.get("pubblicato_il", ""), message=esito.get("messaggio", ""), id=esito.get("id", ""))


@api_v1_prassi.get("/giustizia-amministrativa/testo/pagina")
@_richiedi_auth
def ga_testo_pagina():
    esito = _testo_su_richiesta()
    a = request.args
    titolo = html.escape(f"{a.get('organo', '') or 'Giustizia amministrativa'}, sentenza n. {a.get('numero', '')}/{a.get('anno', '')}"[:200])
    link = (f'<p><a href="{html.escape(esito["url"])}" target="_blank" rel="noopener noreferrer">Apri sul sito ufficiale</a></p>'
            if esito.get("url") else '<p><a href="https://www.giustizia-amministrativa.it/" target="_blank" '
                                     'rel="noopener noreferrer">Sito della Giustizia amministrativa</a></p>')
    if esito.get("ok"):
        fonte = html.escape(esito.get("fonte", ""))
        pubblicato = html.escape(esito.get("pubblicato_il", ""))
        corpo = (f'<p class="nota">Testo integrale dal sito ufficiale ({fonte})'
                 + (f", pubblicato il {pubblicato}" if pubblicato else "") + f".</p>{link}"
                 f'<article>{html.escape(esito["testo"])}</article>')
    else:
        corpo = f'<p class="avviso" role="status">{html.escape(esito.get("messaggio", ""))}</p>{link}'
    pagina = (f'<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, '
              f'initial-scale=1"><title>{titolo}</title><style>body{{font:16px/1.55 Georgia,serif;max-width:52rem;margin:1.5rem auto;'
              'padding:0 1rem;background:#fff;color:#1b1b1b}article{white-space:pre-wrap}.nota{color:#555}.avviso{padding:.75rem;'
              'border:1px solid #c58b00;background:#fff8e1}a{color:#0b4f8a}@media (prefers-color-scheme: dark){body{background:#151515;'
              'color:#e8e8e8}.nota{color:#aaa}.avviso{background:#2b2410}a{color:#8cc4ff}}</style></head>'
              f'<body><h1>{titolo}</h1>{corpo}</body></html>')
    return Response(pagina, mimetype="text/html")


__all__ = ["api_v1_prassi"]
