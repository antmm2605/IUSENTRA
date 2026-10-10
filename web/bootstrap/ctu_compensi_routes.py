"""Rotte del modulo CTU/ausiliari: operazioni peritali, compenso e istanza di liquidazione.

Base normativa: artt. 191-201 c.p.c. e art. 90 disp. att. c.p.c. (operazioni peritali);
D.P.R. 115/2002 artt. 49-58 e 71 con la tabella del D.M. 30/05/2002 (compenso e liquidazione).
Scrittura con ``fascicoli.scrivi``. L'istanza nasce come bozza nell'editor del fascicolo.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify
from web.services.ctu_commands import apply_ctu_change, governed_ctu_write, legacy_ctu_audit, read_ctu_body


def register_ctu_compensi_routes(app: Flask, core: dict[str, Any]) -> None:
    get_ctu = core["get_ctu"]
    get_fascicoli = core["get_fascicoli"]
    audit = core["audit"]

    def _puo() -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente and utente.ha_permesso("fascicoli.scrivi"))
        except Exception:
            return False

    def _incarico(id_fasc: str, incarico_id: str):
        if get_fascicoli().get(id_fasc) is None:
            return None
        incarico = get_ctu().get(incarico_id)
        return incarico if incarico is not None and incarico.fascicolo_id == id_fasc else None

    def _calcola(incarico, dati: dict[str, Any]) -> dict[str, Any]:
        from pct.ctu_compensi.onorari import compenso
        from pct.ctu_compensi.vacazioni import conteggio_giornaliero

        corpo = dict(dati)
        if corpo.get("modalita") == "vacazioni" and not str(corpo.get("vacazioni") or "").strip():
            corpo["vacazioni"] = conteggio_giornaliero(incarico.operazioni)["vacazioni"]
        return compenso(corpo)

    @app.route("/api/v1/ui/ctu/tabella")
    def ctu_tabella_voci():
        from pct.ctu_compensi.tabella_dm_2002 import DECRETO, elenco

        if not g.get("utente_corrente"):
            return jsonify({"ok": False, "message": "Accesso richiesto.", "voci": []}), 403
        return jsonify({"ok": True, "decreto": DECRETO, "voci": elenco()})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/operazioni", methods=["POST"])
    @governed_ctu_write(app)
    def ctu_operazione_nuova(id_fasc: str, incarico_id: str):
        if not _puo():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        if _incarico(id_fasc, incarico_id) is None:
            return jsonify({"ok": False, "message": "Incarico CTU non trovato."}), 404
        dati = read_ctu_body()
        manager = get_ctu()
        apply_ctu_change(manager, "operazione_registrata", dati, fascicolo_id=id_fasc, incarico_id=incarico_id,
                         mutate=lambda: manager.aggiungi_operazione(incarico_id, dati))
        legacy_ctu_audit(manager, audit, "ctu.operazione_registrata", "fascicolo", id_fasc, dettagli=f"{incarico_id}:{dati.get('data')}")
        return jsonify({"ok": True, "message": "Operazione peritale registrata."})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/operazioni/<operazione_id>/rimuovi", methods=["POST"])
    @governed_ctu_write(app)
    def ctu_operazione_rimuovi(id_fasc: str, incarico_id: str, operazione_id: str):
        if not _puo():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        if _incarico(id_fasc, incarico_id) is None:
            return jsonify({"ok": False, "message": "Incarico CTU non trovato."}), 404
        manager = get_ctu()
        dati = read_ctu_body()
        def mutate():
            if not manager.rimuovi_operazione(incarico_id, operazione_id):
                raise ValueError("Operazione già rimossa o non presente nell’incarico. Nessuna nuova modifica registrata.")
        apply_ctu_change(manager, "operazione_rimossa", {**dati, "operazione_id": operazione_id},
                         fascicolo_id=id_fasc, incarico_id=incarico_id, mutate=mutate)
        legacy_ctu_audit(manager, audit, "ctu.operazione_rimossa", "fascicolo", id_fasc, dettagli=f"{incarico_id}:{operazione_id}")
        return jsonify({"ok": True, "message": "Operazione rimossa."})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/compenso", methods=["POST"])
    @governed_ctu_write(app)
    def ctu_compenso(id_fasc: str, incarico_id: str):
        if not _puo():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        incarico = _incarico(id_fasc, incarico_id)
        if incarico is None:
            return jsonify({"ok": False, "message": "Incarico CTU non trovato."}), 404
        dati = read_ctu_body()
        manager = get_ctu()
        def mutate():
            _calcola(manager.get(incarico_id), dati)  # Stesso snapshot del comando.
            manager.salva_compenso(incarico_id, dati)
            return manager.get(incarico_id)
        saved = apply_ctu_change(manager, "compenso_calcolato", dati, fascicolo_id=id_fasc, incarico_id=incarico_id,
                                 mutate=mutate)
        esito = _calcola(saved if saved is not None else incarico, dati)
        legacy_ctu_audit(manager, audit, "ctu.compenso_calcolato", "fascicolo", id_fasc, dettagli=incarico_id)
        return jsonify({**esito, "message": "Compenso calcolato: è la richiesta, la misura la decide il giudice."})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/istanza", methods=["POST"])
    @governed_ctu_write(app)
    def ctu_istanza_liquidazione(id_fasc: str, incarico_id: str):
        from pct.ctu_compensi.istanza import html_istanza
        from pct.fascicoli import TipoDocumento
        from web.services.document_crypto import encrypt_doc

        if not _puo():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        incarico = _incarico(id_fasc, incarico_id)
        fascicolo = get_fascicoli().get(id_fasc)
        if incarico is None or fascicolo is None:
            return jsonify({"ok": False, "message": "Incarico CTU non trovato."}), 404
        if incarico.ruolo_studio != "AUSILIARIO":
            return jsonify({"ok": False, "message": "L'istanza di liquidazione la presenta il consulente d'ufficio."}), 400
        dati = read_ctu_body()
        manager = get_ctu()
        if manager.write_protocol["persistentCommands"]:
            import hashlib
            from pathlib import Path
            from pct.ctu_document_delivery import deliver_liquidation_document
            from pct.document_crypto import decrypt_doc

            documents_dir = get_fascicoli().documents_dir
            def mutate():
                _calcola(manager.get(incarico_id), dati)
                manager.salva_compenso(incarico_id, dati)

            def deliver(conn, saved):
                if saved.get("fascicolo_id") != id_fasc or saved.get("id") != incarico_id:
                    raise ValueError("La bozza CTU appartiene a un incarico differente.")
                return deliver_liquidation_document(conn, saved, tenant=manager._repository.tenant,
                    actor=manager._repository.actor, command_key=dati["commandKey"], documents_dir=documents_dir,
                    calculate=lambda current: _calcola(current, dati))

            apply_ctu_change(manager, "istanza_liquidazione", dati, fascicolo_id=id_fasc, incarico_id=incarico_id,
                             mutate=mutate, delivery=deliver)
            delivered = g._ctu_delivery_result
            if not isinstance(delivered, dict) or delivered.get("kind") != "liquidation_document":
                raise RuntimeError("Riscontro della bozza CTU assente.")
            root = Path(documents_dir).resolve()
            path = (root / delivered["path"]).resolve()
            if not path.is_relative_to(root):
                raise RuntimeError("Percorso della bozza CTU discordante.")
            encrypted = path.read_bytes()
            if (hashlib.sha256(encrypted).hexdigest() != delivered["encrypted_sha256"]
                    or hashlib.sha256(decrypt_doc(encrypted)).hexdigest() != delivered["sha256"]):
                raise RuntimeError("Integrità della bozza CTU non confermata.")
            return jsonify({"ok": True, "message": "Bozza dell’istanza registrata nel fascicolo: rileggila nell’editor prima di firmarla e depositarla.",
                            "url": delivered["url"], "document_id": delivered["document_id"]})
        try:
            calcolo = _calcola(incarico, dati)
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        get_ctu().salva_compenso(incarico_id, dati)
        html = html_istanza(incarico=incarico, fascicolo=fascicolo, calcolo=calcolo,
                            operazioni=sorted(incarico.operazioni, key=lambda o: (o.get("data", ""), o.get("ora", ""))))
        oggi = datetime.now(ZoneInfo("Europe/Rome")).date()
        nome = f"istanza_liquidazione_ctu_{oggi.strftime('%Y%m%d')}.html"
        utente = g.get("utente_corrente")
        documento = get_fascicoli().aggiungi_documento(
            id_fasc, nome, TipoDocumento.ATTO_GIUDIZIARIO, encrypt_doc(html.encode("utf-8")),
            note="Bozza di istanza di liquidazione del CTU (art. 71 D.P.R. 115/2002): rileggere e firmare prima del deposito.",
            tags=["bozza-editor", "ctu", "istanza-liquidazione"], caricato_da=str(getattr(utente, "username", "") or ""),
            fonte_documento="CTU_LIQUIDAZIONE", nome_originale=nome, data_documento=date.isoformat(oggi))
        audit("ctu.istanza_liquidazione", "fascicolo", id_fasc, dettagli=f"{incarico_id}:{documento.id}")
        return jsonify({"ok": True, "message": "Bozza dell'istanza creata nel fascicolo: rileggila nell'editor, firmala e depositala.",
                        "url": f"/fascicoli/{id_fasc}/documenti/{documento.id}/editor", "document_id": documento.id})


__all__ = ["register_ctu_compensi_routes"]
