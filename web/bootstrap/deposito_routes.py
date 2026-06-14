"""Deposit workflow routes extracted from web.app."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_file, url_for

from pct.deposito_simulazione import simulated_deposit_note
from web.blueprints.react_shell import render_react_shell_response
from web.bootstrap.deposito_receipt_routes import register_deposito_receipt_routes
from web.services.local_pec_runtime import (
    deposito_pec_subject,
    local_pec_required_response,
    local_pec_confirmation_result,
    pec_server_send_enabled,
)


def register_deposito_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_config_studio: Callable[[], object],
    audit: Callable[..., None],
    sync_pubblica: Callable[..., None],
    run_deposito_validation: Callable[..., object],
    infer_canale_deposito: Callable[..., str],
    resolve_ufficio_destinatario: Callable[..., dict[str, Any] | None],
    deposito_correction_context: Callable[[object], dict[str, Any]],
    luogo_timbro_firma_visibile: Callable[[], str],
    polis_demo_mode: Callable[[], bool],
) -> None:
    """Register deposito guide pages and deposito workflow routes."""

    register_deposito_receipt_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_config_studio=get_config_studio,
        audit=audit,
    )

    def _ufficio_da_nome(nome_ufficio: str) -> dict[str, Any] | None:
        if not nome_ufficio:
            return None
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            return next(
                (
                    row
                    for row in _get_uff(cache_path).carica()
                    if str(row.get("nome", "")).lower() == nome_ufficio.lower()
                ),
                None,
            )
        except Exception:
            return None

    def _allegati_busta(fascicolo, gestore_fascicoli, id_fascicolo: str, allegati_ids: list[str], allegato_cls):
        allegati = []
        for allegato_id in allegati_ids:
            if not allegato_id:
                continue
            try:
                documento = next((doc for doc in fascicolo.documenti if doc.id == allegato_id), None)
                percorso = str(gestore_fascicoli.percorso_documento(id_fascicolo, allegato_id))
                allegati.append(
                    allegato_cls(
                        percorso=percorso,
                        descrizione=documento.nome if documento else allegato_id,
                    )
                )
            except Exception:
                continue
        return allegati

    def _validation_summary(validation: object) -> dict[str, Any]:
        issues = list(getattr(validation, "issues", []) or [])
        blockers = [issue for issue in issues if isinstance(issue, dict) and issue.get("level") == "BLOCK"]
        warnings = [issue for issue in issues if isinstance(issue, dict) and issue.get("level") == "WARNING"]
        public_issues = [
            {
                "level": str(issue.get("level", "")),
                "code": str(issue.get("code", "")),
                "title": str(issue.get("title", "")),
                "field": str(issue.get("field", "")),
            }
            for issue in issues[:20]
            if isinstance(issue, dict)
        ]
        return {"ok": not blockers, "blockers": len(blockers), "warnings": len(warnings), "issues": public_issues}

    def _guided_transport_completion_response(
        *,
        busta: object,
        id_deposito: str,
        timestamp: str,
        pec_dest: str,
        tipo_atto: str,
        oggetto_pec: str,
        attachment_path: str,
        validation: object,
    ) -> dict[str, Any] | None:
        audit_tecnico = {}
        audit_func = getattr(busta, "audit_conformita_pst", None)
        if callable(audit_func):
            audit_tecnico = audit_func()
        if audit_tecnico.get("uses_real_encryption") is True:
            return None
        next_actions = list(audit_tecnico.get("guided_next_actions") or [])
        if not next_actions:
            algoritmo = str(audit_tecnico.get("required_encryption_algorithm") or "AES256")
            next_actions = [
                "Controlla atto principale, allegati, firme e DatiAtto.xml nel pacchetto preparato.",
                f"Genera o collega Atto.enc ministeriale cifrato {algoritmo}.",
                "Riprendi dal fascicolo per presidiare ricevuta di accettazione, RdAC ed esiti.",
            ]
        return {
            "ok": False,
            "requires_guided_completion": True,
            "package_ready": True,
            "id_deposito": id_deposito,
            "timestamp": timestamp,
            "pec_dest": pec_dest,
            "tipo_atto": tipo_atto,
            "oggetto_pec": oggetto_pec,
            "attachment_path": attachment_path,
            "errore": "Invio diretto sospeso: manca la busta ministeriale conforme.",
            "message": (
                "Il software ha preparato il pacchetto di controllo, ma non registra un deposito come valido "
                "finché Atto.msg non viene cifrato in Atto.enc con algoritmo ministeriale vigente. "
                "Completa il passaggio indicato e poi riprendi il presidio ricevute dal fascicolo."
            ),
            "next_actions": next_actions,
            "validation": _validation_summary(validation),
            "busta_audit": audit_tecnico,
        }

    @app.route("/deposito/checklist")
    def deposito_checklist():
        """Checklist operativa per il deposito telematico."""
        return render_template("deposito_checklist.html")

    @app.route("/guida/firma-digitale")
    def guida_firma_digitale():
        """Guida interattiva per la firma digitale."""
        return render_template("guida_firma_digitale.html")

    @app.route("/fascicoli/<id_fasc>/depositi/aggiungi", methods=["POST"])
    def aggiungi_esito_deposito(id_fasc):
        """Registra manualmente un esito di deposito telematico nel fascicolo."""
        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        try:
            gestore_fascicoli.aggiungi_esito_deposito(
                id_fasc=id_fasc,
                tipo_atto=form.get("tipo_atto", "ATTO"),
                pec_destinatario=form.get("pec_destinatario", ""),
                stato=form.get("stato", "INVIATO"),
                messaggio=form.get("messaggio", ""),
                ricevuta_accettazione=form.get("ricevuta_accettazione", ""),
                ricevuta_consegna=form.get("ricevuta_consegna", ""),
                ricevuta_controlli_automatici=form.get("ricevuta_controlli_automatici", ""),
                esito_controlli=form.get("esito_controlli", ""),
                ricevuta_cancelleria=form.get("ricevuta_cancelleria", ""),
                note=form.get("note", ""),
                registrato_da=utente.username if utente else "",
            )
            flash("Esito deposito registrato nel fascicolo.", "success")
            audit("fascicoli.deposito.aggiungi", "fascicolo", id_fasc)
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=utente.username if utente else "")
        except (ValueError, KeyError) as exc:
            app.logger.warning("Deposito manuale non valido %s: %s", id_fasc, exc)
            flash("Esito deposito non registrato. Verifica i dati e riprova.", "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/depositi/<id_dep>/modifica", methods=["POST"])
    def modifica_esito_deposito(id_fasc, id_dep):
        """Modifica manualmente un esito di deposito telematico nel fascicolo."""
        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        try:
            gestore_fascicoli.modifica_esito_deposito(
                id_fasc=id_fasc,
                id_dep=id_dep,
                tipo_atto=form.get("tipo_atto", "ATTO"),
                pec_destinatario=form.get("pec_destinatario", ""),
                stato=form.get("stato", "INVIATO"),
                messaggio=form.get("messaggio", ""),
                ricevuta_accettazione=form.get("ricevuta_accettazione", ""),
                ricevuta_consegna=form.get("ricevuta_consegna", ""),
                ricevuta_controlli_automatici=form.get("ricevuta_controlli_automatici", ""),
                esito_controlli=form.get("esito_controlli", ""),
                ricevuta_cancelleria=form.get("ricevuta_cancelleria", ""),
                note=form.get("note", ""),
                modificato_da=utente.username if utente else "",
            )
            flash("Deposito aggiornato.", "success")
            audit("fascicoli.deposito.modifica", "fascicolo", id_fasc)
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=utente.username if utente else "")
        except (ValueError, KeyError) as exc:
            app.logger.warning("Modifica deposito non valida %s/%s: %s", id_fasc, id_dep, exc)
            flash("Deposito non aggiornato. Verifica i dati e riprova.", "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/api/fascicoli/<id_fasc>/deposito/valida", methods=["POST"])
    def api_deposito_valida(id_fasc):
        try:
            gestore_fascicoli = get_fascicoli()
            fascicolo = gestore_fascicoli.get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 200
            utente = getattr(g, "utente_corrente", None)
            run = run_deposito_validation(
                fasc=fascicolo,
                gf=gestore_fascicoli,
                form_like=request.form,
                operatore=utente.username if utente else "",
            )
            return jsonify({"ok": True, "validation": run.to_dict()}), 200
        except Exception as exc:
            app.logger.exception("Errore api_deposito_valida: %s", exc)
            return jsonify({"ok": False, "errore": "Validazione deposito non completata. Verifica i dati e riprova."}), 200

    @app.route("/fascicoli/<id_fasc>/deposito/genera-busta", methods=["POST"])
    def deposito_genera_busta(id_fasc):
        """Genera la busta telematica reale e la restituisce come download."""
        import tempfile as _tmp

        from pct.busta import Allegato as AllegatoBusta
        from pct.busta import BustaTelematica, DatiBusta

        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))

        tipo_atto = form.get("tipo_atto", "ATTO").strip()
        codice_registro = form.get("codice_registro", "RG").strip()
        oggetto = (
            form.get("codice_oggetto_pst", "").strip()
            or str(getattr(fascicolo, "codice_oggetto_pst", "") or "").strip()
            or form.get("oggetto", "").strip()
            or fascicolo.titolo
        )
        numero_rg = form.get("numero_rg", "").strip() or (fascicolo.numero_rg or None)
        anno_rg_raw = form.get("anno_rg", "").strip()
        anno_rg = int(anno_rg_raw) if anno_rg_raw.isdigit() else (fascicolo.anno_rg or None)
        atto_id = form.get("atto_principale_id", "").strip()
        allegati_ids = request.form.getlist("allegati_ids")

        validation = run_deposito_validation(
            fasc=fascicolo,
            gf=gestore_fascicoli,
            form_like=request.form,
            operatore=utente.username if utente else "",
        )
        blockers = [issue for issue in validation.issues if issue.get("level") == "BLOCK"]
        if blockers:
            first = blockers[0]
            flash(
                f"Deposito bloccato: {first.get('title')}. {first.get('suggested_action', '')}".strip(),
                "danger",
            )
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

        if not atto_id:
            flash("Seleziona l'atto principale da includere nella busta.", "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

        try:
            atto_path = str(gestore_fascicoli.percorso_documento(id_fasc, atto_id))
        except KeyError:
            flash("Documento principale non trovato nel fascicolo.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        allegati_busta = _allegati_busta(
            fascicolo,
            gestore_fascicoli,
            id_fasc,
            [item for item in allegati_ids if item != atto_id],
            AllegatoBusta,
        )

        ufficio = _ufficio_da_nome(fascicolo.tribunale or "")
        codice_ufficio = str((ufficio or {}).get("codice") or fascicolo.tribunale or "SCONOSCIUTO")

        dati = DatiBusta(
            codice_ufficio=codice_ufficio,
            codice_registro=codice_registro,
            oggetto=oggetto,
            tipo_atto=tipo_atto,
            atto_principale=atto_path,
            allegati=allegati_busta,
            numero_rg=numero_rg,
            anno_rg=anno_rg,
            operatore=utente.username if utente else "",
            cf_mittente="",
        )

        try:
            output_dir = os.getenv("PCT_DEPOSITI_DIR", _tmp.gettempdir())
            busta = BustaTelematica(dati)
            enc_path = busta.crea_busta(output_dir)
            nome_file = f"Busta_{fascicolo.numero.replace('/', '-')}_{tipo_atto}.enc"
            audit(
                "fascicoli.deposito.genera_busta",
                "fascicolo",
                id_fasc,
                dettagli=f"Busta {busta.id_busta[:8]} - {tipo_atto}",
            )
            return send_file(
                enc_path,
                as_attachment=True,
                download_name=nome_file,
                mimetype="application/octet-stream",
            )
        except Exception as exc:
            app.logger.exception("Errore genera_busta %s: %s", id_fasc, exc)
            flash("Errore nella generazione della busta. Verifica documenti e fascicolo.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/deposito/invia-pec", methods=["POST"])
    def deposito_invia_pec(id_fasc):
        """Crea la busta telematica e la invia via PEC all'ufficio giudiziario."""
        import hashlib as _hl
        import json as _json
        import tempfile as _tmp
        import uuid as _uuid
        from datetime import datetime as _dt

        from pct.busta import Allegato as AllegatoBusta
        from pct.busta import BustaTelematica, DatiBusta
        from pct.fascicoli import EsitoDepositoPCT
        from pct.pec import ClientPEC, ConfigPEC as PecCfg

        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 404

        tipo_atto = form.get("tipo_atto", "ATTO").strip()
        codice_registro = form.get("codice_registro", "RG").strip()
        oggetto = (
            form.get("codice_oggetto_pst", "").strip()
            or str(getattr(fascicolo, "codice_oggetto_pst", "") or "").strip()
            or form.get("oggetto", "").strip()
            or fascicolo.titolo
        )
        numero_rg = form.get("numero_rg", "").strip() or (fascicolo.numero_rg or None)
        anno_rg_raw = form.get("anno_rg", "").strip()
        anno_rg = int(anno_rg_raw) if anno_rg_raw.isdigit() else (fascicolo.anno_rg or None)
        atto_id = form.get("atto_principale_id", "").strip()
        allegati_ids = request.form.getlist("allegati_ids")
        note = form.get("note", "").strip()
        canale_deposito = infer_canale_deposito(fascicolo, form.get("canale_deposito", ""))

        validation = run_deposito_validation(
            fasc=fascicolo,
            gf=gestore_fascicoli,
            form_like=request.form,
            operatore=utente.username if utente else "",
        )
        blockers = [issue for issue in validation.issues if issue.get("level") == "BLOCK"]
        if blockers:
            first = blockers[0]
            return jsonify(
                {
                    "ok": False,
                    "errore": f"{first.get('title')}. {first.get('suggested_action', '')}".strip(),
                    "validation": _validation_summary(validation),
                }
            ), 400

        if not atto_id:
            return jsonify({"ok": False, "errore": "Seleziona l'atto principale."}), 400

        try:
            atto_path = str(gestore_fascicoli.percorso_documento(id_fasc, atto_id))
        except KeyError:
            return jsonify({"ok": False, "errore": "Documento principale non trovato."}), 400

        if canale_deposito == "PTT_TRIBUTARIO":
            from pct.fascicoli import AttivitaProcessuale, EsitoAttivita, TIPO_ATTO_LABEL, _tipo_attivita_da_tipo_atto
            from pct.sigit import ClientSIGIT, ClientSIGITDemo

            raw_ufficio = form.get("codice_ufficio", "").strip() or fascicolo.tribunale or ""
            ufficio = resolve_ufficio_destinatario(raw_ufficio)
            codice_commissione = str((ufficio or {}).get("codice") or raw_ufficio or "SCONOSCIUTO")
            nome_commissione = str(
                (ufficio or {}).get("nome")
                or fascicolo.tribunale
                or raw_ufficio
                or "Commissione tributaria"
            )

            cfg_studio = None
            firma_cfg = None
            backend_firma = "nessuno"
            try:
                cfg_studio = get_config_studio().config
                firma_cfg = cfg_studio.firma if cfg_studio and hasattr(cfg_studio, "firma") else None
                backend_firma = getattr(firma_cfg, "backend_firma_effettivo_safe", "nessuno") or "nessuno"
            except Exception:
                cfg_studio = None
                firma_cfg = None

            modalita_demo = True
            client_sigit = ClientSIGITDemo()
            try:
                if backend_firma == "p12" and firma_cfg and getattr(firma_cfg, "p12_path", ""):
                    client_sigit = ClientSIGIT(
                        p12_path=firma_cfg.p12_path,
                        p12_password=(getattr(firma_cfg, "password", "") or "").encode(),
                        codice_fiscale_avvocato=getattr(firma_cfg, "cf_avvocato", "")
                        or os.getenv("PCT_CF_AVVOCATO", ""),
                    )
                    modalita_demo = False
                elif (
                    backend_firma == "pem"
                    and firma_cfg
                    and getattr(firma_cfg, "cert_pem_path", "")
                    and getattr(firma_cfg, "key_pem_path", "")
                ):
                    key_password = (getattr(firma_cfg, "key_pem_password", "") or "").encode() or None
                    client_sigit = ClientSIGIT(
                        cert_pem_path=firma_cfg.cert_pem_path,
                        key_pem_path=firma_cfg.key_pem_path,
                        key_pem_password=key_password,
                        codice_fiscale_avvocato=getattr(firma_cfg, "cf_avvocato", "")
                        or os.getenv("PCT_CF_AVVOCATO", ""),
                    )
                    modalita_demo = False
            except Exception as exc:
                app.logger.warning("Fallback demo SIGIT per %s: %s", id_fasc, exc)
                modalita_demo = True
                client_sigit = ClientSIGITDemo()

            risposta = client_sigit.deposita_atto(
                codice_commissione=codice_commissione,
                tipo_atto=tipo_atto,
                atto_path=atto_path,
                numero_rgt=numero_rg or "",
                anno_rgt=anno_rg or 0,
                oggetto=oggetto,
            )
            if str(risposta.get("codiceEsito", "")).strip() not in {"0", "OK"}:
                return jsonify(
                    {
                        "ok": False,
                        "errore": "Deposito SIGIT non riuscito. Verifica i dati e riprova dal canale ufficiale.",
                        "validation": _validation_summary(validation),
                    }
                ), 400

            id_dep = str(risposta.get("idDeposito") or _uuid.uuid4().hex[:8].upper())
            timestamp = str(risposta.get("dataDeposito") or _dt.now().isoformat())
            ricevuta_accettazione = _json.dumps(
                risposta.get("ricevutaAccettazione") or {},
                ensure_ascii=False,
            )
            esito_controlli = risposta.get("esitoControlli") or {}
            ricevuta_controlli = _json.dumps(esito_controlli, ensure_ascii=False)
            esito_segreteria = risposta.get("esitoCancelleria") or risposta.get("esitoSegreteria") or {}
            ricevuta_cancelleria = _json.dumps(esito_segreteria, ensure_ascii=False)
            tutti_ids = [atto_id] + [aid for aid in allegati_ids if aid != atto_id]
            atto_doc = next((doc for doc in fascicolo.documenti if doc.id == atto_id), None)
            label_atto = TIPO_ATTO_LABEL.get(tipo_atto, tipo_atto)
            messaggio = (
                f"{'[DEMO] ' if modalita_demo else ''}Deposito SIGIT {id_dep} per {nome_commissione}. "
                f"Tipo atto: {tipo_atto}. Procedimento: {numero_rg or 'nuovo'}/{anno_rg or date.today().year}."
            )

            esito = EsitoDepositoPCT(
                id=id_dep,
                timestamp=timestamp,
                stato=str(risposta.get("stato") or "INVIATO"),
                tipo_atto=tipo_atto,
                pec_destinatario=nome_commissione,
                messaggio=messaggio,
                ricevuta_accettazione=ricevuta_accettazione,
                ricevuta_controlli_automatici=ricevuta_controlli,
                esito_controlli=str(esito_controlli.get("codice") or ""),
                ricevuta_cancelleria=ricevuta_cancelleria,
                note=("[SIMULAZIONE DEMO SIGIT] " + note).strip() if modalita_demo else note,
                registrato_da=utente.username if utente else "",
                documenti_ids=tutti_ids,
                nome_atto_principale=atto_doc.nome if atto_doc else "",
            )
            fascicolo.depositi_pct.append(esito)
            for documento in fascicolo.documenti:
                if documento.id in tutti_ids:
                    documento.id_deposito_pct = id_dep
            fascicolo.attivita.append(
                AttivitaProcessuale(
                    id=_uuid.uuid4().hex[:8].upper(),
                    tipo=_tipo_attivita_da_tipo_atto(tipo_atto),
                    data=date.today().isoformat(),
                    titolo=f"Deposito telematico - {label_atto}",
                    descrizione=(
                        f"Tipo atto: {label_atto}. Canale: SIGIT / PTT. "
                        f"Commissione: {nome_commissione}. Deposito: {id_dep}."
                    ),
                    esito=EsitoAttivita.IN_ATTESA,
                    id_deposito_pct=id_dep,
                    avvocato=utente.username if utente else "",
                )
            )
            fascicolo.modificato_il = _dt.now().isoformat()
            gestore_fascicoli._salva()
            audit(
                "fascicoli.deposito.invia_sigit",
                "fascicolo",
                id_fasc,
                dettagli=f"Deposito {id_dep} - {tipo_atto} -> {nome_commissione}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=utente.username if utente else "")
            return jsonify(
                {
                    "ok": True,
                    "demo": bool(modalita_demo),
                    "messaggio": "Deposito registrato nello studio.",
                    "validation": {"ok": True, "blockers": 0, "warnings": 0, "issues": []},
                }
            )

        allegati_busta = _allegati_busta(
            fascicolo,
            gestore_fascicoli,
            id_fasc,
            [item for item in allegati_ids if item != atto_id],
            AllegatoBusta,
        )

        ufficio = _ufficio_da_nome(fascicolo.tribunale or "")
        codice_ufficio = str((ufficio or {}).get("codice") or fascicolo.tribunale or "SCONOSCIUTO")
        pec_dest = str((ufficio or {}).get("pec") or "")
        if not pec_dest:
            return jsonify(
                {
                    "ok": False,
                    "errore": f"Indirizzo PEC non trovato per '{fascicolo.tribunale}'. Verifica il tribunale nel fascicolo.",
                }
            ), 400

        pec_cfg = None
        modalita_demo = False
        try:
            from pct.config_studio import GestioneConfigStudio as _GCS

            gestore_config = _GCS(app.config.get("STUDIO_CONFIG", "./config/studio.json"))
            studio_cfg = gestore_config.config
            pec_cfg = studio_cfg.pec if studio_cfg else None
            if not pec_cfg or not pec_cfg.indirizzo:
                modalita_demo = True
                pec_cfg = None
        except Exception:
            modalita_demo = True
            pec_cfg = None

        try:
            dati = DatiBusta(
                codice_ufficio=codice_ufficio,
                codice_registro=codice_registro,
                oggetto=oggetto,
                tipo_atto=tipo_atto,
                atto_principale=atto_path,
                allegati=allegati_busta,
                numero_rg=numero_rg,
                anno_rg=anno_rg,
                operatore=utente.username if utente else "",
                cf_mittente=getattr(pec_cfg, "cf_mittente", "") or "",
            )
            output_dir = os.getenv("PCT_DEPOSITI_DIR", _tmp.gettempdir())
            busta = BustaTelematica(dati)
            enc_path = busta.crea_busta(output_dir)
        except Exception as exc:
            app.logger.exception("Errore creazione busta %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": "Creazione busta non completata. Verifica documenti e fascicolo."}), 500

        id_dep = form.get("local_pec_id_deposito", "").strip() or busta.id_busta[:8].upper()
        timestamp = _dt.now().isoformat()
        oggetto_pec = deposito_pec_subject(
            tipo_atto=tipo_atto,
            numero_rg=numero_rg,
            anno_rg=anno_rg,
            tribunale=fascicolo.tribunale or "",
        )
        guided_response = _guided_transport_completion_response(
            busta=busta,
            id_deposito=id_dep,
            timestamp=timestamp,
            pec_dest=pec_dest,
            tipo_atto=tipo_atto,
            oggetto_pec=oggetto_pec,
            attachment_path=enc_path,
            validation=validation,
        )
        if guided_response:
            return jsonify(guided_response), 409

        if modalita_demo:
            fake_mid = _hl.sha256(f"{id_dep}{timestamp}".encode()).hexdigest()[:16].upper()
            ris = {
                "inviato": True,
                "message_id": f"PROVA-{fake_mid}@iusentra.invalid",
                "demo": True,
            }
            app.logger.info("Deposito di prova %s - busta creata senza invio PEC reale", id_dep)
        elif form.get("local_pec_confirmed") == "1":
            try:
                ris = local_pec_confirmation_result(form.get("local_pec_message_id", ""))
            except ValueError as exc:
                app.logger.warning("Conferma Local Signer non valida per deposito %s: %s", id_dep, exc)
                return jsonify({"ok": False, "errore": "Conferma Local Signer non valida. Ripeti l'invio dal PC locale."}), 400
            app.logger.info("Deposito %s confermato da invio PEC Local Signer", id_dep)
        elif not pec_server_send_enabled():
            return jsonify(
                local_pec_required_response(
                    pec_cfg=pec_cfg,
                    pec_dest=pec_dest,
                    tipo_atto=tipo_atto,
                    id_deposito=id_dep,
                    timestamp=timestamp,
                    oggetto_pec=oggetto_pec,
                    attachment_path=enc_path,
                    validation=validation,
                )
            )
        else:
            try:
                config_pec = PecCfg(
                    indirizzo=pec_cfg.indirizzo,
                    password=pec_cfg.password,
                    smtp_host=getattr(pec_cfg, "smtp_host", "smtp.pec.aruba.it"),
                    smtp_port=getattr(pec_cfg, "smtp_port", 465),
                    imap_host=getattr(pec_cfg, "imap_host", ""),
                    imap_port=getattr(pec_cfg, "imap_port", 993),
                    use_ssl=getattr(pec_cfg, "use_ssl", True),
                )
                client_pec = ClientPEC(config_pec)
                ris = client_pec.invia_busta(
                    destinatario_pec=pec_dest,
                    busta_path=enc_path,
                    oggetto=oggetto_pec,
                )
                if not ris.get("inviato"):
                    app.logger.warning("Invio PEC non completato per deposito %s", id_dep)
                    return jsonify({"ok": False, "errore": "Invio PEC non completato. Verifica casella e credenziali."}), 500
            except Exception as exc:
                app.logger.exception("Errore invio PEC %s: %s", id_fasc, exc)
                return jsonify({"ok": False, "errore": "Invio PEC non completato. Verifica casella e credenziali."}), 500

        try:
            from datetime import datetime as _dtnow

            from pct.fascicoli import AttivitaProcessuale, EsitoAttivita, TIPO_ATTO_LABEL, _tipo_attivita_da_tipo_atto

            msg_demo = "Prova senza invio reale - " if modalita_demo else ""
            atto_doc = next((doc for doc in fascicolo.documenti if doc.id == atto_id), None)
            tutti_ids = [atto_id] + [aid for aid in allegati_ids if aid != atto_id]
            esito = EsitoDepositoPCT(
                id=id_dep,
                timestamp=timestamp,
                stato="INVIATO",
                tipo_atto=tipo_atto,
                pec_destinatario=pec_dest,
                messaggio=(
                    f"{msg_demo}Busta {id_dep} predisposta verso {pec_dest}. Nessun invio esterno eseguito."
                    if modalita_demo
                    else f"Busta {id_dep} inviata via PEC a {pec_dest}. Message-ID: {ris.get('message_id', '')}"
                ),
                note=simulated_deposit_note(note) if modalita_demo else note,
                registrato_da=utente.username if utente else "",
                documenti_ids=tutti_ids,
                nome_atto_principale=atto_doc.nome if atto_doc else "",
            )
            fascicolo.depositi_pct.append(esito)
            for documento in fascicolo.documenti:
                if documento.id in tutti_ids:
                    documento.id_deposito_pct = id_dep

            label_atto = TIPO_ATTO_LABEL.get(tipo_atto, tipo_atto)
            fascicolo.attivita.append(
                AttivitaProcessuale(
                    id=__import__("uuid").uuid4().hex[:8].upper(),
                    tipo=_tipo_attivita_da_tipo_atto(tipo_atto),
                    data=date.today().isoformat(),
                    titolo=f"Deposito telematico - {label_atto}",
                    descrizione=f"Tipo atto: {label_atto}. PEC: {pec_dest}. Busta: {id_dep}.",
                    esito=EsitoAttivita.IN_ATTESA,
                    id_deposito_pct=id_dep,
                    avvocato=utente.username if utente else "",
                )
            )
            fascicolo.modificato_il = _dtnow.now().isoformat()
            gestore_fascicoli._salva()
            audit(
                "fascicoli.deposito.invia_pec",
                "fascicolo",
                id_fasc,
                dettagli=f"Deposito {id_dep} - {tipo_atto} -> {pec_dest}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=utente.username if utente else "")
        except Exception as exc:
            app.logger.exception("Errore salvataggio esito PEC %s: %s", id_fasc, exc)
            return jsonify(
                {
                    "ok": True,
                    "demo": modalita_demo,
                    "avviso": "Busta inviata, ma il salvataggio dell'esito non è stato completato.",
                    "id_deposito": id_dep,
                    "pec_dest": pec_dest,
                    "tipo_atto": tipo_atto,
                }
            )

        return jsonify(
            {
                "ok": True,
                "demo": modalita_demo,
                "id_deposito": id_dep,
                "pec_dest": pec_dest,
                "tipo_atto": tipo_atto,
                "timestamp": timestamp,
            }
        )

    @app.route("/fascicoli/<id_fasc>/deposito/prepara", methods=["GET"])
    def deposito_prepara(id_fasc):
        """Mostra il riepilogo documenti e la guida al deposito telematico."""
        if (request.args.get("_legacy") or "").strip().lower() not in {"1", "true", "si", "yes", "on"}:
            return render_react_shell_response(f"fascicoli/{id_fasc}/deposito/prepara")

        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))

        ufficio = _ufficio_da_nome(fascicolo.tribunale or "")
        pec_tribunale = str((ufficio or {}).get("pec") or "")

        pdfa_stato: dict[str, Any] = {}
        try:
            from pct.validazione import verifica_dimensione, verifica_pdfa

            for documento in fascicolo.documenti:
                try:
                    percorso = str(gestore_fascicoli.percorso_documento(id_fasc, documento.id))
                    pdfa = verifica_pdfa(percorso)
                    dimensione = verifica_dimensione(percorso)
                    pdfa_stato[documento.id] = {**pdfa, "dimensione": dimensione}
                except Exception:
                    continue
        except Exception:
            pass

        pec_configurata = False
        try:
            cfg = get_config_studio().config
            pec_configurata = bool(cfg and cfg.pec and cfg.pec.indirizzo and cfg.pec.password)
        except Exception:
            cfg = None
            pass
        firma_cfg = getattr(cfg, "firma", None) if cfg else None

        return render_template(
            "fascicoli/deposito_prepara.html",
            fascicolo=fascicolo,
            pec_tribunale=pec_tribunale,
            pec_configurata=pec_configurata,
            pdfa_stato=pdfa_stato,
            correction_context=deposito_correction_context(fascicolo),
            firma_visibile_place=luogo_timbro_firma_visibile(),
            firma_visibile_mode=getattr(firma_cfg, "visible_signature_mode", "laterale"),
            oggi=date.today(),
        )

    @app.route("/fascicoli/<id_fasc>/deposito/invia", methods=["POST"])
    def deposito_invia(id_fasc):
        """Crea la busta telematica e la invia via PEC all'ufficio giudiziario."""
        import tempfile as _tmp
        import uuid as _uuid
        from datetime import datetime as _dt

        from pct.fascicoli import EsitoDepositoPCT

        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))

        demo_mode = form.get("demo_mode") == "1" or polis_demo_mode()
        tipo_atto = form.get("tipo_atto", "ATTO").strip()
        codice_registro = form.get("codice_registro", "RG").strip()
        numero_rg = form.get("numero_rg", "").strip()
        anno_rg_str = form.get("anno_rg", "").strip()
        oggetto = (
            form.get("codice_oggetto_pst", "").strip()
            or str(getattr(fascicolo, "codice_oggetto_pst", "") or "").strip()
            or form.get("oggetto", "").strip()
            or fascicolo.titolo
        )
        note = form.get("note", "").strip()
        tribunale_nome = form.get("tribunale_nome", "").strip()
        tribunale_pec = form.get("tribunale_pec", "").strip()
        codice_ufficio = form.get("codice_ufficio", "").strip()
        atto_id = form.get("atto_principale_id", "").strip()
        allegati_ids = request.form.getlist("allegati_ids")

        validation = run_deposito_validation(
            fasc=fascicolo,
            gf=gestore_fascicoli,
            form_like=request.form,
            operatore=utente.username if utente else "",
        )
        blockers = [issue for issue in validation.issues if issue.get("level") == "BLOCK"]
        if blockers:
            first = blockers[0]
            return jsonify(
                {
                    "ok": False,
                    "errore": f"{first.get('title')}. {first.get('suggested_action', '')}".strip(),
                    "validation": _validation_summary(validation),
                }
            ), 400

        if not tribunale_nome:
            flash("Seleziona un ufficio giudiziario destinatario.", "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))
        if not atto_id:
            flash("Seleziona l'atto principale da includere nella busta.", "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

        anno_rg = int(anno_rg_str) if anno_rg_str.isdigit() else (fascicolo.anno_rg or 0)
        id_dep = form.get("local_pec_id_deposito", "").strip() or _uuid.uuid4().hex[:8].upper()
        timestamp = _dt.now().isoformat()

        if demo_mode:
            pec_prova = tribunale_pec or f"{tribunale_nome.lower().replace(' ', '.')}@pec.prova.invalid"
            esito = EsitoDepositoPCT(
                id=id_dep,
                timestamp=timestamp,
                stato="INVIATO",
                tipo_atto=tipo_atto,
                pec_destinatario=pec_prova,
                messaggio=(
                    f"Prova deposito senza invio reale: busta {id_dep} predisposta per {tribunale_nome}. "
                    f"Atto: {tipo_atto} - RG {numero_rg}/{anno_rg}."
                ),
                note=simulated_deposit_note(note),
                registrato_da=utente.username if utente else "prova",
            )
        else:
            try:
                from pct.busta import Allegato as AllegatoBusta
                from pct.busta import BustaTelematica, DatiBusta
                from pct.deposito import DepositoCivile
                from pct.firma import crea_signer_da_config
                from pct.pec import ConfigPEC

                atto_doc = next((doc for doc in fascicolo.documenti if doc.id == atto_id), None)
                if not atto_doc:
                    flash("Documento selezionato come atto principale non trovato.", "danger")
                    return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

                atto_path = str(gestore_fascicoli.percorso_documento(id_fasc, atto_id))
                allegati_busta = _allegati_busta(
                    fascicolo,
                    gestore_fascicoli,
                    id_fasc,
                    [item for item in allegati_ids if item != atto_id],
                    AllegatoBusta,
                )

                dati = DatiBusta(
                    codice_ufficio=codice_ufficio or tribunale_nome,
                    codice_registro=codice_registro,
                    oggetto=oggetto,
                    tipo_atto=tipo_atto,
                    atto_principale=atto_path,
                    allegati=allegati_busta,
                    numero_rg=numero_rg or None,
                    anno_rg=anno_rg or None,
                    operatore=utente.username if utente else "",
                    cf_mittente="",
                )

                cfg_studio = get_config_studio().config
                pec_cfg = cfg_studio.pec if cfg_studio and hasattr(cfg_studio, "pec") else None
                firma_cfg = cfg_studio.firma if cfg_studio and hasattr(cfg_studio, "firma") else None
                if not pec_cfg or not pec_cfg.indirizzo:
                    raise RuntimeError(
                        "Configurazione PEC non trovata. Configura le credenziali PEC nelle impostazioni."
                    )

                config_pec = ConfigPEC(
                    indirizzo=pec_cfg.indirizzo,
                    password=pec_cfg.password,
                    smtp_host=getattr(pec_cfg, "smtp_host", "smtp.pec.provider.it"),
                    smtp_port=getattr(pec_cfg, "smtp_port", 465),
                    imap_host=getattr(pec_cfg, "imap_host", ""),
                    imap_port=getattr(pec_cfg, "imap_port", 993),
                )

                firma = None
                if firma_cfg:
                    try:
                        backend_firma = firma_cfg.backend_firma_effettivo
                    except Exception as exc:
                        backend_firma = "nessuno"
                        app.logger.warning("Backend firma non disponibile: %s", exc)
                    if backend_firma == "pkcs11":
                        app.logger.info(
                            "Firma PKCS#11 selezionata: il deposito web usa il flusso CAdES in-device dedicato."
                        )
                    elif backend_firma in ("p12", "pem"):
                        try:
                            firma = crea_signer_da_config(firma_cfg)
                        except Exception as exc:
                            app.logger.warning("Signer non inizializzato: %s", exc)

                output_dir = os.getenv("PCT_DEPOSITI_DIR", _tmp.gettempdir())
                deposito_civile = DepositoCivile(config_pec=config_pec, firma=firma, output_dir=output_dir)

                pec_dest = tribunale_pec
                if not pec_dest and codice_ufficio:
                    try:
                        from pct.uffici_giudiziari import get_gestore as _get_uff

                        cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                        ufficio = next(
                            (
                                row
                                for row in _get_uff(cache_path).carica()
                                if row.get("codice") == codice_ufficio
                            ),
                            None,
                        )
                        pec_dest = str((ufficio or {}).get("pec") or "")
                    except Exception:
                        pass

                if not pec_dest:
                    raise RuntimeError(
                        f"Indirizzo PEC non trovato per l'ufficio '{tribunale_nome}'. "
                        "Verifica la selezione o imposta manualmente la PEC."
                    )

                oggetto_pec = deposito_pec_subject(
                    tipo_atto=tipo_atto,
                    numero_rg=numero_rg or None,
                    anno_rg=anno_rg or None,
                    tribunale=tribunale_nome,
                )
                if not pec_server_send_enabled():
                    from pathlib import Path as _Path

                    output_dir = os.getenv("PCT_DEPOSITI_DIR", _tmp.gettempdir())
                    busta_dir = _Path(output_dir) / id_dep
                    busta = BustaTelematica(dati)
                    busta_path = busta.crea_busta(str(busta_dir))
                    guided_response = _guided_transport_completion_response(
                        busta=busta,
                        id_deposito=id_dep,
                        timestamp=timestamp,
                        pec_dest=pec_dest,
                        tipo_atto=tipo_atto,
                        oggetto_pec=oggetto_pec,
                        attachment_path=busta_path,
                        validation=validation,
                    )
                    if guided_response:
                        return jsonify(guided_response), 409
                    if form.get("local_pec_confirmed") != "1":
                        return jsonify(
                            local_pec_required_response(
                                pec_cfg=pec_cfg,
                                pec_dest=pec_dest,
                                tipo_atto=tipo_atto,
                                id_deposito=id_dep,
                                timestamp=timestamp,
                                oggetto_pec=oggetto_pec,
                                attachment_path=busta_path,
                                validation=validation,
                            )
                        )

                    ris_locale = local_pec_confirmation_result(form.get("local_pec_message_id", ""))
                    esito = EsitoDepositoPCT(
                        id=id_dep,
                        timestamp=timestamp,
                        stato="INVIATO",
                        tipo_atto=tipo_atto,
                        pec_destinatario=pec_dest,
                        messaggio=(
                            f"Busta {id_dep} inviata via PEC dal PC locale tramite Local Signer. "
                            f"Message-ID: {ris_locale.get('message_id', '')}"
                        ),
                        note=note,
                        registrato_da=utente.username if utente else "",
                        busta_path=busta_path,
                    )
                else:
                    esito_dep = deposito_civile.deposita(
                        dati=dati,
                        tribunale=codice_ufficio or tribunale_nome,
                        attendi_ricevute=False,
                    )
                    deposito_civile.salva_esito(esito_dep)

                    esito = EsitoDepositoPCT(
                        id=esito_dep.id_deposito,
                        timestamp=esito_dep.timestamp,
                        stato=esito_dep.stato,
                        tipo_atto=tipo_atto,
                        pec_destinatario=esito_dep.pec_destinatario,
                        messaggio=esito_dep.messaggio,
                        ricevuta_accettazione=esito_dep.ricevuta_accettazione or "",
                        ricevuta_consegna=esito_dep.ricevuta_consegna or "",
                        note=note,
                        registrato_da=utente.username if utente else "",
                        busta_path=esito_dep.busta_path,
                    )
            except Exception as exc:
                app.logger.exception("Errore deposito_invia %s: %s", id_fasc, exc)
                flash("Deposito non completato. Verifica il canale ufficiale e riprova.", "danger")
                return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

        try:
            from datetime import datetime as _dtnow

            documenti_deposito_ids = [atto_id] + [aid for aid in allegati_ids if aid and aid != atto_id]
            if not getattr(esito, "documenti_ids", None):
                esito.documenti_ids = documenti_deposito_ids
            fascicolo.depositi_pct.append(esito)
            for documento in fascicolo.documenti:
                if documento.id in documenti_deposito_ids:
                    documento.id_deposito_pct = esito.id
            fascicolo.modificato_il = _dtnow.now().isoformat()
            gestore_fascicoli._salva()
            audit(
                "fascicoli.deposito.invia",
                "fascicolo",
                id_fasc,
                dettagli=f"Deposito {esito.id} - {tipo_atto} verso {esito.pec_destinatario}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=utente.username if utente else "")
            if demo_mode:
                flash(
                    f"Deposito di prova registrato con ID {esito.id}. Nessun messaggio PEC è stato spedito.",
                    "warning",
                )
            else:
                flash(
                    f"Deposito {esito.id} inviato via PEC a {esito.pec_destinatario}. Ricevute di accettazione e consegna saranno disponibili a breve.",
                    "success",
                )
        except Exception as exc:
            app.logger.exception("Errore salvataggio esito deposito %s: %s", id_fasc, exc)
            flash("Deposito inviato, ma il salvataggio dell'esito non è stato completato.", "warning")

        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
