"""Route fascicolo ↔ registro di cancelleria e ricevute pagoPA.

Estratte da ``polisweb_routes`` per il limite di governabilita' dei moduli
bootstrap: aggancio RG dal registro, pannello variazioni, caricamento della
Ricevuta Telematica pagoPA. Regole PST invariate: nessuna sessione salvata,
nessun download autonomo, verifiche fail-closed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify, request


_ROME_TZ = ZoneInfo("Europe/Rome")


def _format_rt_data_it(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "n.d."
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(_ROME_TZ)
    if parsed.hour == parsed.minute == parsed.second == parsed.microsecond == 0:
        return parsed.strftime("%d/%m/%Y")
    return parsed.strftime("%d/%m/%Y %H:%M")


def register_fascicolo_registro_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    audit: Callable[..., None],
    polis_auth_mode: Callable[[], str],
) -> None:
    @app.route("/fascicoli/<id_fasc>/cerca-rg-registro", methods=["POST"])
    def fascicolo_cerca_rg_registro(id_fasc):
        from web.services.polisweb_fascicolo_sync import cerca_rg_nel_registro

        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            esito = cerca_rg_nel_registro(
                id_fasc,
                get_fascicoli=get_fascicoli,
                get_clienti=get_clienti,
                auth_mode=polis_auth_mode(),
            )
        except Exception as exc:
            app.logger.exception("Errore ricerca RG registro %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "message": f"Ricerca non riuscita: {exc}"}), 200
        return jsonify(esito)

    @app.route("/fascicoli/<id_fasc>/aggancia-rg", methods=["POST"])
    def fascicolo_aggancia_rg(id_fasc):
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        payload = request.get_json(silent=True) or request.form
        numero_rg = str(payload.get("numeroRg") or payload.get("numero_rg") or "").strip()
        anno_rg = str(payload.get("annoRg") or payload.get("anno_rg") or "").strip()
        if not numero_rg or not anno_rg.isdigit():
            return jsonify({"ok": False, "message": "Numero e anno di ruolo non validi."}), 400
        try:
            get_fascicoli().aggiorna(id_fasc, numero_rg=numero_rg, anno_rg=int(anno_rg))
            audit("polisweb.aggancia_rg", "fascicolo", id_fasc, dettagli=f"RG {numero_rg}/{anno_rg}")
        except Exception as exc:
            return jsonify({"ok": False, "message": f"Aggancio RG non riuscito: {exc}"}), 200
        message = f"RG {numero_rg}/{anno_rg} agganciato al fascicolo dal registro."
        return jsonify({"ok": True, "message": message, "messaggio": message})

    @app.route("/api/v1/ui/fascicoli/<id_fasc>/registro-cancelleria")
    def fascicolo_registro_cancelleria(id_fasc):
        """Pannello «Registro di cancelleria»: ultimo allineamento e storico differenze."""
        from web.services.polisweb_fascicolo_sync import _diff_repository

        utente = g.utente_corrente
        if not utente:
            return jsonify({"ok": False, "message": "Accesso richiesto."}), 403
        try:
            gestore = get_fascicoli()
            fascicolo = gestore.get(id_fasc)
            if fascicolo is None:
                return jsonify({"ok": False, "message": "Fascicolo non trovato."}), 404
            diff_repo = _diff_repository(gestore)
            return jsonify({
                "ok": True,
                "lastSyncAt": str(getattr(fascicolo, "last_sync_at", "") or ""),
                "syncStatus": str(getattr(fascicolo, "sync_status", "") or ""),
                "monitorato": diff_repo.ha_snapshot(id_fasc),
                "differenze": diff_repo.storico(id_fasc, limite=20),
            })
        except Exception as exc:
            app.logger.exception("Errore pannello registro %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "message": "Pannello registro non disponibile.", "differenze": []}), 200

    @app.route("/fascicoli/<id_fasc>/ricevuta-pagamento", methods=["POST"])
    def fascicolo_carica_ricevuta_pagamento(id_fasc):
        """Carica una Ricevuta Telematica pagoPA nel fascicolo, verificandola.

        Il download della RT avviene sul portale ufficiale con autenticazione
        dell'avvocato (regole PST: niente sessioni salvate ne' download
        autonomo); qui il file scaricato viene letto, verificato secondo lo
        schema ministeriale PagamentiTelematiciGiustizia e archiviato tra i
        documenti del fascicolo con l'esito in nota.
        """
        from pct.fascicoli import TipoDocumento
        from pct.pagamenti_giustizia import format_importo_euro_it, parse_rt

        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        gestore = get_fascicoli()
        fascicolo = gestore.get(id_fasc)
        if fascicolo is None:
            return jsonify({"ok": False, "message": "Fascicolo non trovato."}), 404
        upload = request.files.get("ricevuta")
        if upload is None or not upload.filename:
            return jsonify({"ok": False, "message": "Nessun file ricevuta selezionato."}), 400
        nome = Path(upload.filename).name
        if not nome.casefold().endswith((".xml", ".xml.p7m")):
            return jsonify({
                "ok": False,
                "message": "La ricevuta telematica è il file RT in formato XML (anche firmato .p7m) scaricato dal portale pagamenti.",
            }), 400
        contenuto = upload.read()
        if len(contenuto) > 2 * 1024 * 1024:
            return jsonify({"ok": False, "message": "File troppo grande per essere una ricevuta telematica."}), 400
        try:
            rt = parse_rt(contenuto)
        except Exception:
            rt = None
        if rt is None:
            return jsonify({
                "ok": False,
                "message": "Il file non è una Ricevuta Telematica PagoPA valida (schema PagamentiTelematiciGiustizia).",
            }), 400
        importo_rt = format_importo_euro_it(rt.importo_totale)
        data_rt = _format_rt_data_it(rt.data_ricevuta)
        nota = (
            f"Ricevuta telematica PagoPA - esito: {rt.esito_label}; importo {importo_rt}; "
            f"IUV {rt.iuv or 'n.d.'}; data {data_rt}"
        )
        try:
            documento = gestore.aggiungi_documento(
                id_fasc,
                nome,
                TipoDocumento.ALLEGATO,
                contenuto,
                note=nota,
                caricato_da=getattr(utente, "username", "") or "",
                fonte_documento="pagopa_rt",
            )
        except Exception as exc:
            return jsonify({"ok": False, "message": f"Archiviazione non riuscita: {exc}"}), 200
        audit(
            "pagamenti.ricevuta_rt",
            "fascicolo",
            id_fasc,
            dettagli=f"{nome}: {rt.esito_label}, {importo_rt}, IUV {rt.iuv or 'n.d.'}",
        )
        message = (
            f"Ricevuta verificata e archiviata nel fascicolo: {rt.esito_label}, "
            f"{importo_rt} (IUV {rt.iuv or 'n.d.'})."
        )
        if not rt.pagamento_eseguito:
            message += " Attenzione: la ricevuta non prova un pagamento eseguito."
        return jsonify({
            "ok": True,
            "message": message,
            "messaggio": message,
            "ricevuta": rt.to_dict(),
            "documento_id": getattr(documento, "id", ""),
        })
