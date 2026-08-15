"""Route della prima nota di studio (registro cronologico di cassa).

Shell React su /prima-nota; scritture con audit. Il registro non si riscrive:
le correzioni passano dallo storno motivato.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request

from web.blueprints.react_shell import render_react_shell_response


def register_prima_nota_routes(app: Flask, core: dict[str, Any]) -> None:
    get_prima_nota = core["get_prima_nota"]
    get_fatturazione = core["get_fatturazione"]
    audit = core["audit"]

    def _permesso(scrittura: bool = False) -> bool:
        utente = g.get("utente_corrente")
        chiave = "fatturazione.scrivi" if scrittura else "fatturazione.leggi"
        try:
            return bool(utente and utente.ha_permesso(chiave))
        except Exception:
            return False

    @app.route("/prima-nota")
    def prima_nota_page():
        return render_react_shell_response("prima-nota")

    @app.route("/api/v1/ui/prima-nota")
    def prima_nota_payload():
        from web.services.react_prima_nota_bridge import build_react_prima_nota_payload

        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            return jsonify(
                build_react_prima_nota_payload(get_prima_nota=get_prima_nota, query=request.args)
            )
        except Exception as exc:
            app.logger.exception("Errore payload prima nota: %s", exc)
            return jsonify({"ok": False, "message": "Prima nota non disponibile."}), 200

    @app.route("/prima-nota/registra", methods=["POST"])
    def prima_nota_registra():
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        utente = g.get("utente_corrente")
        try:
            movimento = get_prima_nota().registra(
                data=str(dati.get("data") or ""),
                tipo=str(dati.get("tipo") or ""),
                importo=dati.get("importo"),
                categoria=str(dati.get("categoria") or ""),
                controparte=str(dati.get("controparte") or ""),
                causale=str(dati.get("causale") or ""),
                metodo=str(dati.get("metodo") or "banca"),
                fascicolo_id=str(dati.get("fascicoloId") or ""),
                documento_riferimento=str(dati.get("documento") or ""),
                creato_da=getattr(utente, "username", "") or "",
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("prima_nota.registrato", "prima_nota", movimento.id, dettagli=f"{movimento.tipo} {movimento.importo}")
        message = f"Movimento registrato: {movimento.tipo.lower()} di {movimento.importo:.2f} EUR."
        return jsonify({"ok": True, "message": message, "messaggio": message, "movimentoId": movimento.id})

    @app.route("/prima-nota/<movimento_id>/storna", methods=["POST"])
    def prima_nota_storna(movimento_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        utente = g.get("utente_corrente")
        try:
            storno = get_prima_nota().storna(
                movimento_id,
                motivo=str(dati.get("motivo") or ""),
                attore=getattr(utente, "username", "") or "",
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("prima_nota.stornato", "prima_nota", movimento_id, dettagli=storno.causale)
        return jsonify({"ok": True, "message": "Storno registrato: il movimento originale resta a registro."})

    @app.route("/prima-nota/riconcilia-parcelle", methods=["POST"])
    def prima_nota_riconcilia():
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        utente = g.get("utente_corrente")
        try:
            creati = get_prima_nota().incassi_da_parcelle(
                get_fatturazione(), attore=getattr(utente, "username", "") or ""
            )
        except Exception as exc:
            app.logger.exception("Errore riconciliazione prima nota: %s", exc)
            return jsonify({"ok": False, "message": f"Riconciliazione non riuscita: {exc}"}), 200
        audit("prima_nota.riconciliazione", "prima_nota", "parcelle", dettagli=f"{len(creati)} incassi")
        message = (
            f"{len(creati)} incassi importati dalle parcelle pagate."
            if creati
            else "Nessuna parcella pagata da importare: registro gia' allineato."
        )
        return jsonify({"ok": True, "message": message, "messaggio": message, "creati": len(creati)})

    @app.route("/prima-nota/riconciliazione/analizza", methods=["POST"])
    def prima_nota_riconciliazione_analizza():
        """Analizza l'estratto conto CSV e propone gli abbinamenti (mai automatici)."""
        from pct.riconciliazione_bancaria import parse_estratto_csv, proponi_abbinamenti

        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        upload = request.files.get("estratto")
        if upload is None or not upload.filename:
            return jsonify({"ok": False, "message": "Seleziona il file CSV dell'estratto conto."}), 400
        if len(upload.filename) > 200 or not upload.filename.casefold().endswith((".csv", ".txt")):
            return jsonify({"ok": False, "message": "Formato non supportato: esporta l'estratto conto in CSV dall'home banking."}), 400
        contenuto = upload.read(2 * 1024 * 1024 + 1)
        if len(contenuto) > 2 * 1024 * 1024:
            return jsonify({"ok": False, "message": "File oltre 2 MB: esporta un periodo piu' breve."}), 400
        try:
            testo = contenuto.decode("utf-8-sig")
        except UnicodeDecodeError:
            testo = contenuto.decode("latin-1", errors="replace")
        righe, avvisi = parse_estratto_csv(testo)
        if not righe:
            return jsonify({"ok": False, "message": " ".join(avvisi) or "Nessun movimento leggibile nel file."}), 400
        registro = get_prima_nota()
        proposte = proponi_abbinamenti(righe, registro.registro())
        movimenti_index = {m.id: m for m in registro.registro()}

        def _movimento_breve(mid: str) -> dict[str, Any]:
            m = movimenti_index.get(mid)
            return {
                "id": mid,
                "data": getattr(m, "data", ""),
                "importo": float(getattr(m, "importo", 0.0)),
                "causale": getattr(m, "causale", "") or getattr(m, "controparte", ""),
            } if m else {"id": mid}

        payload = [
            {
                "riga": {
                    "id": p.riga.id,
                    "data": p.riga.data,
                    "importo": p.riga.importo,
                    "descrizione": p.riga.descrizione,
                    "verso": p.riga.verso,
                },
                "tipo": p.tipo,
                "movimento": _movimento_breve(p.movimento_id) if p.movimento_id else None,
                "candidati": [_movimento_breve(mid) for mid in p.candidati],
            }
            for p in proposte
        ]
        audit("prima_nota.riconciliazione_analisi", "prima_nota", "estratto", dettagli=f"{len(righe)} righe, {len(avvisi)} avvisi")
        conteggi = {
            "abbinamenti": sum(1 for p in proposte if p.tipo == "abbinamento"),
            "ambigui": sum(1 for p in proposte if p.tipo == "ambiguo"),
            "nuovi": sum(1 for p in proposte if p.tipo == "nuovo_movimento"),
        }
        return jsonify({"ok": True, "proposte": payload, "avvisi": avvisi, "conteggi": conteggi})

    @app.route("/prima-nota/riconciliazione/conferma", methods=["POST"])
    def prima_nota_riconciliazione_conferma():
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        importo_raw = dati.get("importoRiga")
        try:
            importo_riga = float(importo_raw) if importo_raw is not None else None
        except (TypeError, ValueError):
            importo_riga = None
        try:
            movimento = get_prima_nota().marca_riconciliato(
                str(dati.get("movimentoId") or ""),
                riga_estratto_id=str(dati.get("rigaId") or ""),
                importo_riga=importo_riga,
                verso_riga=str(dati.get("versoRiga") or ""),
            )
        except KeyError:
            return jsonify({"ok": False, "message": "Movimento non trovato."}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("prima_nota.riconciliato", "prima_nota", movimento.id, dettagli=f"riga={movimento.riga_estratto_id}")
        return jsonify({"ok": True, "message": "Movimento riconciliato con l'estratto conto."})

    @app.route("/prima-nota/riconciliazione/registra-da-riga", methods=["POST"])
    def prima_nota_registra_da_riga():
        """Registra un movimento da una riga banca e lo marca riconciliato.

        Idempotente per riga: se la riga ha gia' generato un movimento non si
        duplica. Chiude il cerchio: il movimento nasce dalla banca, quindi
        nasce gia' riconciliato con quella riga.
        """
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        riga_id = str(dati.get("rigaId") or "").strip()
        if not riga_id:
            return jsonify({"ok": False, "message": "Riga estratto mancante."}), 400
        registro = get_prima_nota()
        if any(m.riga_estratto_id == riga_id for m in registro.registro()):
            return jsonify({"ok": True, "message": "Riga gia' registrata in prima nota: nessun doppione creato."})
        utente = g.get("utente_corrente")
        verso = str(dati.get("verso") or "")
        try:
            movimento = registro.registra(
                data=str(dati.get("data") or ""),
                tipo=verso,
                importo=abs(float(dati.get("importo") or 0)),
                categoria="altri_incassi" if verso == "INCASSO" else "altri_pagamenti",
                causale=str(dati.get("descrizione") or "Da estratto conto")[:240],
                metodo="banca",
                creato_da=getattr(utente, "username", "") or "",
            )
            registro.marca_riconciliato(movimento.id, riga_estratto_id=riga_id)
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("prima_nota.registrato_da_banca", "prima_nota", movimento.id, dettagli=f"riga={riga_id}")
        message = "Movimento registrato dalla riga bancaria (gia' riconciliato): classifica la categoria dal registro."
        return jsonify({"ok": True, "message": message, "messaggio": message, "movimentoId": movimento.id})

    @app.route("/prima-nota/esporta.csv")
    def prima_nota_esporta():
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        csv_text = get_prima_nota().esporta_csv(
            dal=str(request.args.get("dal") or ""),
            al=str(request.args.get("al") or ""),
        )
        audit("prima_nota.export", "prima_nota", "csv", dettagli="export commercialista")
        return Response(
            "﻿" + csv_text,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=prima-nota.csv"},
        )
