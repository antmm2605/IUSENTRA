"""Route della prima nota di studio (registro cronologico di cassa).

Shell React su /prima-nota; scritture con audit. Il registro non si riscrive:
le correzioni passano dallo storno motivato.
"""

from __future__ import annotations

from typing import Any
from functools import wraps

from flask import Flask, Response, g, jsonify, request

from web.blueprints.react_shell import render_react_shell_response
from pct.prima_nota_repository import PrimaNotaConflict
from pct.pagamenti_giustizia import format_importo_euro_it


def register_prima_nota_routes(app: Flask, core: dict[str, Any]) -> None:
    get_prima_nota = core["get_prima_nota"]
    get_fatturazione = core["get_fatturazione"]
    audit = core["audit"]

    def _validation_error(exc):
        conflict = isinstance(exc, PrimaNotaConflict)
        return jsonify({"ok": False, "message": str(exc), "code": "conflict" if conflict else "validation"}), 409 if conflict else 400

    def _governed_write(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except PrimaNotaConflict as exc:
                return _validation_error(exc)
            except Exception:
                app.logger.exception("Esito comando Prima nota non confermato: %s", function.__name__)
                # Un errore può avvenire dopo la persistenza (rilascio lock/audit).
                # Non autorizzare un retry cieco né affermare che nulla è salvato.
                message = (
                    'Esito del salvataggio da verificare. La bozza è conservata: usa “Verifica salvataggio” per recuperare la conferma.'
                    if function.__name__ == 'prima_nota_registra' and g.get('prima_nota_persistent_recovery', False) else
                    'Esito del comando non confermato. Ricarica il registro e controlla il movimento prima di riprovare.'
                )
                return jsonify({"ok": False, "code": "outcome_not_confirmed", "message": message}), 503
        return wrapped

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
            return jsonify({"ok": False, "message": "Prima nota non disponibile. Il registro esistente è preservato; riprova il caricamento."}), 503

    @app.route("/prima-nota/registra", methods=["POST"])
    @_governed_write
    def prima_nota_registra():
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        utente = g.get("utente_corrente")
        try:
            registro = get_prima_nota()
            protocol = registro.write_protocol
            protected = protocol['persistentCommands']
            g.prima_nota_persistent_recovery = protected
            if protected and ('expectedRevision' not in dati or not dati.get('commandKey')):
                return jsonify({'ok': False, 'code': 'precondition_required', 'message':
                    'Ricarica il registro prima di registrare il movimento; la bozza è preservata.'}), 428
            if protected and (type(dati.get('expectedRevision')) is not int or dati['expectedRevision'] < 0):
                raise ValueError('Revisione del registro non valida.')
            movement_command = {}
            if protected or 'commandKey' in dati or 'expectedRevision' in dati:
                movement_command = {'command_key': dati.get('commandKey', ''),
                                    'expected_revision': dati.get('expectedRevision')}
            movimento = registro.registra(
                **movement_command,
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
            return _validation_error(exc)
        if registro.write_protocol['persistentCommands']:
            registro.confirm_audit(movimento.id)
        else:
            audit("prima_nota.registrato", "prima_nota", movimento.id, dettagli=f"{movimento.tipo} {format_importo_euro_it(movimento.importo)}")
        message = f"Movimento registrato: {movimento.tipo.lower()} di {format_importo_euro_it(movimento.importo)}."
        return jsonify({"ok": True, "message": message, "messaggio": message, "movimentoId": movimento.id, "writeProtocol": registro.write_protocol})

    @app.route("/prima-nota/<movimento_id>/storna", methods=["POST"])
    @_governed_write
    def prima_nota_storna(movimento_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        utente = g.get("utente_corrente")
        try:
            registro = get_prima_nota()
            storno = registro.storna(
                movimento_id,
                motivo=str(dati.get("motivo") or ""),
                attore=getattr(utente, "username", "") or "",
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except ValueError as exc:
            return _validation_error(exc)
        if registro.write_protocol['persistentCommands']:
            registro.confirm_audit(storno.id)
        else:
            audit("prima_nota.stornato", "prima_nota", movimento_id, dettagli=storno.causale)
        return jsonify({"ok": True, "message": "Storno registrato: il movimento originale resta a registro."})

    @app.route("/prima-nota/riconcilia-parcelle", methods=["POST"])
    @_governed_write
    def prima_nota_riconcilia():
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        utente = g.get("utente_corrente")
        try:
            registro = get_prima_nota()
            creati = registro.incassi_da_parcelle(
                get_fatturazione(), attore=getattr(utente, "username", "") or ""
            )
        except ValueError as exc:
            return _validation_error(exc)
        if registro.write_protocol['persistentCommands']:
            for movimento in creati:
                registro.confirm_audit(movimento.id)
        else:
            audit("prima_nota.riconciliazione", "prima_nota", "parcelle", dettagli=f"{len(creati)} incassi")
        message = (
            f"{len(creati)} incassi importati dalle parcelle pagate."
            if creati
            else "Nessuna parcella pagata da importare: registro già allineato."
        )
        return jsonify({"ok": True, "message": message, "messaggio": message, "creati": len(creati)})

    @app.route("/prima-nota/riconciliazione/analizza", methods=["POST"])
    @_governed_write
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
    @_governed_write
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
            registro = get_prima_nota()
            movimento = registro.marca_riconciliato(
                str(dati.get("movimentoId") or ""),
                riga_estratto_id=str(dati.get("rigaId") or ""),
                importo_riga=importo_riga,
                verso_riga=str(dati.get("versoRiga") or ""),
            )
        except KeyError:
            return jsonify({"ok": False, "message": "Movimento non trovato."}), 404
        except ValueError as exc:
            return _validation_error(exc)
        if registro.write_protocol['persistentCommands']:
            registro.confirm_audit(movimento.id)
        else:
            audit("prima_nota.riconciliato", "prima_nota", movimento.id, dettagli=f"riga={movimento.riga_estratto_id}")
        return jsonify({"ok": True, "message": "Movimento riconciliato con l'estratto conto."})

    @app.route("/prima-nota/riconciliazione/registra-da-riga", methods=["POST"])
    @_governed_write
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
        utente = g.get("utente_corrente")
        verso = str(dati.get("verso") or "")
        try:
            movimento = registro.registra_da_riga(
                riga_estratto_id=riga_id,
                data=str(dati.get("data") or ""),
                tipo=verso,
                importo=abs(float(dati.get("importo") or 0)),
                categoria="altri_incassi" if verso == "INCASSO" else "altri_pagamenti",
                causale=str(dati.get("descrizione") or "Da estratto conto")[:240],
                metodo="banca",
                creato_da=getattr(utente, "username", "") or "",
            )
        except (TypeError, ValueError) as exc:
            return _validation_error(exc)
        if registro.write_protocol['persistentCommands']:
            registro.confirm_audit(movimento.id)
        else:
            audit("prima_nota.registrato_da_banca", "prima_nota", movimento.id, dettagli=f"riga={riga_id}")
        categoria_label = "Altri incassi" if verso == "INCASSO" else "Altri pagamenti"
        message = f"Movimento bancario registrato e riconciliato. Categoria: {categoria_label}."
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
