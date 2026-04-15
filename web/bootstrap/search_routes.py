"""Search and OCR queue routes extracted from web.app."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Any

from flask import Flask, g, jsonify, render_template, request


def register_search_routes(
    app: Flask,
    *,
    get_indice: Callable[[], object],
    get_clienti: Callable[[], object],
    get_fascicoli: Callable[[], object],
    get_agenda: Callable[[], object],
    get_scadenziario: Callable[[], object],
    audit: Callable[..., None],
    ocr_supportato: Callable[[str], bool],
    accoda_ocr: Callable[..., Any],
    ocr_queue: queue.Queue,
    ocr_stats: dict[str, Any],
    ocr_stats_lock: threading.Lock,
) -> None:
    """Register search, index rebuild, and OCR worker state routes."""

    @app.route("/api/cerca")
    def api_cerca():
        try:
            q = request.args.get("q", "").strip()
            tipi_raw = request.args.getlist("tipo")
            limit = min(int(request.args.get("limit", 20)), 50)
            if not q:
                return jsonify([])
            indice = get_indice()
            risultati = indice.cerca(q, tipi=tipi_raw or None, limit=limit)
            return jsonify(
                [
                    {
                        "tipo": r.tipo,
                        "id": r.id,
                        "titolo": r.titolo,
                        "sottotitolo": r.sottotitolo,
                        "url": r.url,
                        "icona": r.icona,
                        "snippet": r.snippet,
                    }
                    for r in risultati
                ]
            )
        except Exception as e:
            app.logger.exception("Errore api_cerca: %s", e)
            return jsonify([])

    @app.route("/cerca")
    def cerca():
        q = request.args.get("q", "").strip()
        risultati = {}
        if q:
            indice = get_indice()
            risultati = indice.cerca_globale(q, limit=30)
        return render_template("cerca.html", q=q, risultati=risultati)

    @app.route("/api/ricerca/ricostruisci", methods=["POST"])
    def api_ricerca_ricostruisci():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        try:
            indice = get_indice()
            gf = get_fascicoli()
            documenti_ocr = []
            for fasc in gf.tutti():
                d = fasc.to_dict() if hasattr(fasc, "to_dict") else fasc
                for doc in d.get("documenti", []):
                    testo = indice.get_ocr_cache(doc.get("hash_sha256", ""))
                    if testo:
                        documenti_ocr.append(
                            (
                                d["id"],
                                doc["id"],
                                doc.get("nome", ""),
                                testo,
                                doc.get("tipo", ""),
                            )
                        )
                    elif ocr_supportato(doc.get("nome", "")):
                        try:
                            percorso = str(gf.percorso_documento(d["id"], doc["id"]))
                            accoda_ocr(
                                percorso=percorso,
                                hash_sha256=doc.get("hash_sha256", ""),
                                id_fasc=d["id"],
                                id_doc=doc["id"],
                                nome_doc=doc.get("nome", ""),
                                tipo_doc=doc.get("tipo", ""),
                                index_path=app.config["SEARCH_INDEX"],
                            )
                        except Exception:
                            pass
            indice.ricostruisci(
                clienti=get_clienti().tutti(),
                fascicoli=gf.tutti(),
                appuntamenti=get_agenda().tutti(),
                scadenze=get_scadenziario().tutte(solo_aperte=False),
                documenti_ocr=documenti_ocr,
            )
            audit("ricerca.ricostruisci_indice")
            return jsonify({"ok": True, "statistiche": indice.statistiche()})
        except Exception as e:
            app.logger.exception("Errore api_ricerca_ricostruisci: %s", e)
            return jsonify({"ok": False, "errore": str(e)})

    @app.route("/api/ocr/stato")
    def api_ocr_stato():
        try:
            with ocr_stats_lock:
                stats = dict(ocr_stats)
            stats["in_coda"] = ocr_queue.qsize()
            return jsonify(stats)
        except Exception as e:
            return jsonify({"errore": str(e)}), 200
