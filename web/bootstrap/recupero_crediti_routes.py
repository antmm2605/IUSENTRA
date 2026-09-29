"""Rotte del recupero crediti in serie (pagina /recupero-crediti).

Lettura con ``fascicoli.leggi``, scrittura con ``fascicoli.scrivi``. Logica in
``web.services.recupero_crediti_runtime`` e nel dominio ``pct.recupero_crediti``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify, request

from web.blueprints.react_shell import render_react_shell_response


def _oggi() -> date:
    return datetime.now(ZoneInfo("Europe/Rome")).date()


def register_recupero_crediti_routes(app: Flask, core: dict[str, Any]) -> None:
    get_config_studio = core["get_config_studio"]
    get_fascicoli = core["get_fascicoli"]
    get_clienti = core["get_clienti"]
    get_scadenziario = core["get_scadenziario"]
    audit = core["audit"]

    def _puo(permesso: str) -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente and utente.ha_permesso(permesso))
        except Exception:
            return False

    def _archivio():
        from pct.recupero_crediti.archivio import ArchivioRecupero

        return ArchivioRecupero.accanto_a(get_config_studio().percorso)

    def _conta(posizione):
        from pct.recupero_crediti.conteggi import conteggio
        from pct.strumenti_legali import GestioneStrumentiLegali

        gestore = GestioneStrumentiLegali(normative_db_path=app.config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json"))
        return conteggio(posizione, _oggi(), gestore.calcola_interessi)

    def _ids() -> list[str]:
        dati = request.get_json(silent=True) or {}
        ids = dati.get("ids") if isinstance(dati.get("ids"), list) else []
        return [str(i) for i in ids][:500]

    @app.route("/recupero-crediti")
    def recupero_crediti_pagina():
        return render_react_shell_response("recupero-crediti")

    @app.route("/api/v1/ui/recupero-crediti")
    def recupero_crediti_payload():
        from pct.recupero_crediti.modello import STATI
        from pct.recupero_crediti.stati import PASSAGGI
        from web.services.recupero_crediti_runtime import MODELLI_ATTO, riepilogo

        if not _puo("fascicoli.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        posizioni = _archivio().tutte()
        return jsonify({
            "ok": True, "puoModificare": _puo("fascicoli.scrivi"), "riepilogo": riepilogo(posizioni),
            "posizioni": [p.to_dict() for p in posizioni],
            "stati": [{"value": k, "label": v} for k, v in STATI.items()], "passaggi": PASSAGGI,
            "atti": [{"value": k, "label": v[1]} for k, v in MODELLI_ATTO.items()],
            "creditori": [{"value": c.id, "label": c.nome_completo} for c in get_clienti().tutti()[:2000]],
        })

    @app.route("/api/v1/ui/recupero-crediti/<pid>/conteggio")
    def recupero_crediti_conteggio(pid: str):
        if not _puo("fascicoli.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        posizione = _archivio().get(pid)
        if posizione is None:
            return jsonify({"ok": False, "message": "Posizione non trovata."}), 404
        try:
            return jsonify({"ok": True, **_conta(posizione)})
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.route("/recupero-crediti/importa", methods=["POST"])
    def recupero_crediti_importa():
        from pct.recupero_crediti.importazione import leggi_csv
        from web.services.recupero_crediti_runtime import importa

        if not _puo("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        creditore_id = str(request.form.get("creditore_id") or "").strip()
        cliente = get_clienti().get(creditore_id) if creditore_id else None
        if cliente is None:
            return jsonify({"ok": False, "message": "Scegli il creditore fra i clienti dello studio."}), 400
        upload = request.files.get("file")
        if upload is None:
            return jsonify({"ok": False, "message": "Carica il file CSV con l'elenco dei debitori."}), 400
        contenuto = upload.read(5 * 1024 * 1024 + 1)
        if len(contenuto) > 5 * 1024 * 1024:
            return jsonify({"ok": False, "message": "Il file supera 5 MB: dividilo in più lotti."}), 400
        lotto = str(request.form.get("lotto") or "").strip()[:80] or f"Lotto del {_oggi().strftime('%d/%m/%Y')}"
        posizioni, errori = leggi_csv(contenuto, creditore_id=cliente.id, creditore=cliente.nome_completo, lotto=lotto)
        esito = importa(_archivio(), posizioni) if posizioni else {"importate": 0, "gia_presenti": 0, "ids": []}
        audit("recupero_crediti.importato", "recupero_crediti", lotto, dettagli=f"importate={esito['importate']} errori={len(errori)}")
        messaggio = f"{esito['importate']} posizioni importate" + (f", {esito['gia_presenti']} già presenti" if esito["gia_presenti"] else "") \
            + (f", {len(errori)} righe da correggere" if errori else "") + "."
        return jsonify({"ok": bool(posizioni), "message": messaggio, "errori": errori[:50], **esito}), 200 if posizioni else 400

    @app.route("/recupero-crediti/fascicoli", methods=["POST"])
    def recupero_crediti_fascicoli():
        from pct.fascicoli import TipoFascicolo
        from web.services.recupero_crediti_runtime import apri_fascicoli

        if not _puo("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403

        def nuovo(posizione):
            return get_fascicoli().nuovo(f"{posizione.creditore} c. {posizione.debitore} — recupero crediti", TipoFascicolo.CIVILE,
                                         id_cliente=posizione.creditore_id, nome_cliente=posizione.creditore,
                                         oggetto="Recupero del credito (artt. 633 ss. c.p.c.)")

        aperti = apri_fascicoli(_archivio(), _ids(), nuovo_fascicolo=nuovo)
        audit("recupero_crediti.fascicoli", "recupero_crediti", "lotto", dettagli=f"aperti={aperti}")
        return jsonify({"ok": True, "message": f"{aperti} fascicoli aperti." if aperti else "Nessun fascicolo da aprire.", "aperti": aperti})

    @app.route("/recupero-crediti/atti", methods=["POST"])
    def recupero_crediti_atti():
        from pct.compilatore_atti import get_modello, prefill_payload, render_compiled_act
        from web.blueprints.template_atti import _importa_compilazione_editor_professionale
        from web.services.recupero_crediti_runtime import genera_atti

        if not _puo("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        tipo = str((request.get_json(silent=True) or {}).get("tipo") or "")

        def base(posizione):
            fascicolo = get_fascicoli().get(posizione.fascicolo_id)
            cliente = get_clienti().get(posizione.creditore_id)
            codice = {"diffida": "STR_MM_001", "ricorso": "CIV_RDI_001", "precetto": "CIV_PREC_001"}[tipo]
            return prefill_payload(codice, fascicolo=fascicolo, cliente=cliente, utente=g.get("utente_corrente"))

        def crea_bozza(codice, payload, posizione):
            testo = render_compiled_act(codice, payload)
            creato = _importa_compilazione_editor_professionale(model_code=codice, model=get_modello(codice) or {}, payload=payload,
                                                                testo_generato=testo, selected_fascicolo=get_fascicoli().get(posizione.fascicolo_id),
                                                                requested_draft="working_draft", confirmed_warning=True)
            return str((creato or {}).get("document_id") or "")

        try:
            esito = genera_atti(_archivio(), _ids(), tipo, oggi=_oggi(), conta=_conta, crea_bozza=crea_bozza, base_payload=base)
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("recupero_crediti.atti", "recupero_crediti", tipo, dettagli=f"create={esito['create']}")
        messaggio = f"{esito['create']} bozze create nei fascicoli: rileggile nell'editor prima di firmarle." + (
            f" {len(esito['saltate'])} posizioni saltate." if esito["saltate"] else "")
        return jsonify({"ok": True, "message": messaggio, **esito})

    @app.route("/recupero-crediti/avanza", methods=["POST"])
    def recupero_crediti_avanza():
        from pct.scadenziario import TipoTermine
        from web.services.recupero_crediti_runtime import avanza

        if not _puo("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or {}
        try:
            data_evento = date.fromisoformat(str(dati.get("data") or ""))
        except ValueError:
            return jsonify({"ok": False, "message": "Indica la data dell'evento."}), 400
        if data_evento > _oggi():
            return jsonify({"ok": False, "message": "La data dell'evento non può essere futura."}), 400
        utente = g.get("utente_corrente")

        def crea_scadenza(posizione, termine):
            marcatore = f"RECUPERO:{posizione.id}:{termine['codice']}:{data_evento.isoformat()}"
            scadenziario = get_scadenziario()
            if any(marcatore in str(getattr(s, "note", "") or "") for s in scadenziario.tutte(solo_aperte=False)):
                return
            scadenziario.nuova(titolo=f"{termine['titolo']} — {posizione.debitore}", tipo=TipoTermine.TERMINE_PERENTORIO,
                               data_scadenza=termine["data"], id_fascicolo=posizione.fascicolo_id, data_decorrenza=data_evento.isoformat(),
                               perentorio=True, id_utente_responsabile=str(getattr(utente, "id", "") or ""),
                               descrizione=f"Recupero crediti: {termine['norma']}", note=marcatore, giorni_preavviso=[15, 7, 3, 1, 0])

        try:
            esito = avanza(_archivio(), _ids(), str(dati.get("stato") or ""), data_evento, nota=str(dati.get("nota") or "")[:300],
                           utente=str(getattr(utente, "username", "") or ""), crea_scadenza=crea_scadenza)
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("recupero_crediti.avanzamento", "recupero_crediti", str(dati.get("stato") or ""), dettagli=f"aggiornate={esito['aggiornate']}")
        messaggio = f"{esito['aggiornate']} posizioni aggiornate, {esito['scadenze']} scadenze create." + (
            f" {len(esito['rifiutate'])} non spostate." if esito["rifiutate"] else "")
        return jsonify({"ok": True, "message": messaggio, **esito})
