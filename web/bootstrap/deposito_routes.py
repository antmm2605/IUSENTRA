"""Deposit workflow routes extracted from web.app."""
from __future__ import annotations
import os
from collections.abc import Callable
from datetime import date
from typing import Any
from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_file, url_for
from pct.deposito_telematico_catalogo import resolve_deposit_type_payload
from pct.pst_cifratura import PSTCifraturaError
from web.blueprints.react_shell import render_react_shell_response
from web.bootstrap.deposito_legacy_send_routes import register_deposito_legacy_send_route
from web.bootstrap.deposito_receipt_routes import register_deposito_receipt_routes
from web.services.deposito_route_helpers import (
    allegati_busta as _allegati_busta,
    deposito_oggetto as _deposito_oggetto,
    guided_transport_completion_response as _guided_transport_completion_response,
    manual_deposito_payload as _manual_deposito_payload,
    ufficio_deposito_destinatario as _ufficio_deposito_destinatario,
    ufficio_da_nome as _ufficio_da_nome,
    validate_busta_document_selection as _validate_busta_document_selection,
    validation_summary as _validation_summary,
    wants_json_response as _wants_json_response,
)
from web.services.local_pec_runtime import (
    deposito_pec_subject,
    local_pec_required_response,
    local_pec_confirmation_result,
    resolve_deposito_pec_body,
)
from web.services.deposito_pec_runtime import (
    build_compatibility_report as _build_compatibility_report,
    build_simulazione_pec_payload as _build_simulazione_pec_payload,
    con_avviso_pec_mittente as _aggiungi_avviso_pec_mittente,
    registra_prova_senza_invio_pec as _registra_prova_senza_invio_pec,
)
from web.services.deposito_signature_runtime import (
    dati_atto_signature_gate as _dati_atto_signature_gate,
    documenti_busta_nomi as _documenti_busta_nomi,
)
from web.services.deposito_anagrafica_ministeriale import (
    anagrafica_xml_se_ricorso as _anagrafica_xml_se_ricorso,
    valore_causa_fascicolo as _valore_causa_fascicolo,
)
from web.services.security_redaction import redacted_json_response


def _deposito_catalogo_entry(form_like: Any) -> tuple[dict[str, Any] | None, str]:
    key = str(form_like.get("tipo_deposito_telematico_key", "") or "").strip()
    if not key:
        return None, ""
    entry = resolve_deposit_type_payload(key)
    if not entry:
        return None, "Tipo deposito Studio Telematico non trovato nel catalogo backend."
    return entry, ""


def _deposito_catalogo_apply(entry: dict[str, Any] | None, tipo_atto: str, codice_registro: str) -> tuple[str, str]:
    if not entry:
        return tipo_atto, codice_registro
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    return (
        str(payload.get("tipo_atto") or tipo_atto).strip() or tipo_atto,
        str(payload.get("codice_registro") or codice_registro).strip() or codice_registro,
    )


def _deposito_catalogo_blocker(entry: dict[str, Any] | None, *, require_real_package: bool) -> str:
    if not entry:
        return ""
    rules = entry.get("rules") if isinstance(entry.get("rules"), dict) else {}
    if not bool(rules.get("can_prepare_in_pct_panel", True)):
        return str(
            rules.get("real_send_blocker")
            or "Questo tipo Studio Telematico appartiene a un canale diverso dal deposito PCT civile."
        )
    if require_real_package and not bool(rules.get("real_send_allowed_from_pct_panel", True)):
        return str(
            rules.get("real_send_blocker")
            or "Per questo tipo deposito serve completare il generatore DatiAtto ministeriale specifico."
        )
    return ""


def register_deposito_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_clienti: Callable[[], Any],
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
    @app.route("/deposito/checklist")
    def deposito_checklist():
        """Checklist operativa per il deposito telematico."""
        return render_template("deposito_checklist.html")
    @app.route("/guida/firma-digitale")
    def guida_firma_digitale():
        """Guida interattiva per la firma digitale."""
        return render_template("guida_firma_digitale.html")
    register_deposito_legacy_send_route(
        app,
        get_fascicoli=get_fascicoli,
        get_config_studio=get_config_studio,
        audit=audit,
        sync_pubblica=sync_pubblica,
        run_deposito_validation=run_deposito_validation,
        polis_demo_mode=polis_demo_mode,
        documenti_busta_nomi=_documenti_busta_nomi,
    )
    @app.route("/fascicoli/<id_fasc>/depositi/aggiungi", methods=["POST"])
    def aggiungi_esito_deposito(id_fasc):
        """Registra manualmente un esito di deposito telematico nel fascicolo."""
        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        try:
            actor = utente.username if utente else ""
            gestore_fascicoli.aggiungi_esito_deposito(
                id_fasc=id_fasc,
                **_manual_deposito_payload(form, actor, actor_key="registrato_da"),
            )
            flash("Esito deposito registrato nel fascicolo.", "success")
            audit("fascicoli.deposito.aggiungi", "fascicolo", id_fasc)
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=actor)
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
            actor = utente.username if utente else ""
            gestore_fascicoli.modifica_esito_deposito(
                id_fasc=id_fasc,
                id_dep=id_dep,
                **_manual_deposito_payload(form, actor, actor_key="modificato_da"),
            )
            flash("Deposito aggiornato.", "success")
            audit("fascicoli.deposito.modifica", "fascicolo", id_fasc)
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=actor)
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
    @app.route("/api/v1/ui/fascicoli/<id_fasc>/deposito/certificato-cifratura", methods=["GET", "POST"])
    def api_deposito_certificato_cifratura(id_fasc):
        """Controlla o salva il .cer PST usato per cifrare Atto.msg in Atto.enc."""
        from base64 import b64decode
        from binascii import Error as Base64Error
        from dataclasses import asdict
        from pct.pst_cifratura import (
            PSTCifraturaError as _PSTCifraturaError,
            certificato_cifratura_in_cache,
            salva_certificato_cifratura_ufficio,
        )
        try:
            fascicolo = get_fascicoli().get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 404
            if request.method == "GET":
                codice = str(request.args.get("codice_ufficio") or "").strip()
                if not codice:
                    return jsonify({"ok": False, "errore": "Codice ufficio mancante."}), 400
                info = certificato_cifratura_in_cache(codice)
                return jsonify({
                    "ok": True,
                    "codice_ufficio": codice,
                    "cached": bool(info),
                    "certificato": asdict(info) if info else None,
                })
            payload_json = request.get_json(silent=True) or {}
            codice = str(payload_json.get("codice_ufficio") or "").strip()
            certificato_b64 = str(payload_json.get("certificato_b64") or "").strip()
            source_url = str(payload_json.get("source_url") or "").strip()
            if not codice:
                return jsonify({"ok": False, "errore": "Codice ufficio mancante."}), 400
            if not certificato_b64:
                return jsonify({"ok": False, "errore": "Certificato PST mancante."}), 400
            try:
                payload = b64decode(certificato_b64, validate=True)
            except (Base64Error, ValueError) as exc:
                raise _PSTCifraturaError("Certificato PST non codificato correttamente.") from exc
            info = salva_certificato_cifratura_ufficio(codice, payload, source_url=source_url)
            utente = getattr(g, "utente_corrente", None)
            audit(
                "fascicoli.deposito.certificato_cifratura",
                "fascicolo",
                id_fasc,
                utente=getattr(utente, "username", None),
                dettagli=f"Certificato PST {codice} salvato ({info.sha256[:12]})",
            )
            return jsonify({
                "ok": True,
                "codice_ufficio": codice,
                "cached": True,
                "certificato": asdict(info),
            })
        except _PSTCifraturaError as exc:
            app.logger.warning("Certificato PST deposito non accettato %s: %s", id_fasc, exc)
            return jsonify(
                {
                    "ok": False,
                    "errore": "Certificato PST non valido o non compatibile con l'ufficio indicato.",
                }
            ), 400
        except Exception as exc:
            app.logger.exception("Certificato PST deposito non salvato %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": "Certificato PST non salvato. Verifica Local Signer e riprova."}), 500
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
        catalog_entry, catalog_error = _deposito_catalogo_entry(form)
        if catalog_error:
            if _wants_json_response(request.headers):
                return jsonify({"ok": False, "errore": catalog_error}), 400
            flash(catalog_error, "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))
        tipo_atto, codice_registro = _deposito_catalogo_apply(catalog_entry, tipo_atto, codice_registro)
        catalog_blocker = _deposito_catalogo_blocker(catalog_entry, require_real_package=True)
        if catalog_blocker:
            if _wants_json_response(request.headers):
                return jsonify({"ok": False, "package_ready": False, "errore": catalog_blocker}), 400
            flash(catalog_blocker, "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))
        oggetto = _deposito_oggetto(form, fascicolo)
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
        selection_error = _validate_busta_document_selection(
            fascicolo,
            gestore_fascicoli,
            id_fasc,
            form,
            atto_id,
            allegati_ids,
        )
        if selection_error:
            if _wants_json_response(request.headers):
                return jsonify({"ok": False, "errore": selection_error}), 400
            flash(selection_error, "danger")
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
        ufficio_deposito = _ufficio_deposito_destinatario(fascicolo)
        codice_ufficio = str(ufficio_deposito.get("codice_ufficio") or "SCONOSCIUTO")
        try:
            anagrafica_xml = _anagrafica_xml_se_ricorso(
                tipo_atto=tipo_atto,
                fascicolo=fascicolo,
                get_clienti=get_clienti,
                get_config_studio=get_config_studio,
                operatore=utente.username if utente else "",
            )
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))
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
            valore_causa=_valore_causa_fascicolo(fascicolo),
            anagrafica_procedimento_xml=anagrafica_xml,
        )
        try:
            output_dir = os.getenv("PCT_DEPOSITI_DIR", _tmp.gettempdir())
            busta = BustaTelematica(dati)
            enc_path = busta.crea_busta(output_dir)
            nome_file = "Atto.enc"
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
        except PSTCifraturaError as exc:
            app.logger.exception("Certificato PST/cifratura busta non completata %s: %s", id_fasc, exc)
            flash("Busta non generata: certificato PST o cifratura ministeriale da verificare.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        except Exception as exc:
            app.logger.exception("Errore genera_busta %s: %s", id_fasc, exc)
            flash("Errore nella generazione della busta. Verifica documenti e fascicolo.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
    @app.route("/fascicoli/<id_fasc>/deposito/indice-documenti", methods=["GET", "POST"])
    def deposito_indice_documenti(id_fasc):
        """Genera l'anteprima PDF dell'indice documenti sulla selezione corrente."""
        from io import BytesIO as _BytesIO
        from pct.busta import Allegato as AllegatoBusta
        from pct.busta import BustaTelematica, DatiBusta, INDICE_DOCUMENTI_FILENAME
        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.values
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 404
        tipo_atto = form.get("tipo_atto", "ATTO").strip()
        codice_registro = form.get("codice_registro", "RG").strip()
        catalog_entry, catalog_error = _deposito_catalogo_entry(form)
        if catalog_error:
            return jsonify({"ok": False, "errore": catalog_error}), 400
        tipo_atto, codice_registro = _deposito_catalogo_apply(catalog_entry, tipo_atto, codice_registro)
        catalog_blocker = _deposito_catalogo_blocker(catalog_entry, require_real_package=False)
        if catalog_blocker:
            return jsonify({"ok": False, "errore": catalog_blocker}), 400
        oggetto = _deposito_oggetto(form, fascicolo)
        numero_rg = form.get("numero_rg", "").strip() or (fascicolo.numero_rg or None)
        anno_rg_raw = form.get("anno_rg", "").strip()
        anno_rg = int(anno_rg_raw) if anno_rg_raw.isdigit() else (fascicolo.anno_rg or None)
        atto_id = form.get("atto_principale_id", "").strip()
        allegati_ids = form.getlist("allegati_ids")
        if not atto_id:
            return jsonify({"ok": False, "errore": "Seleziona l'atto principale prima di visualizzare l'indice."}), 400
        selection_error = _validate_busta_document_selection(
            fascicolo,
            gestore_fascicoli,
            id_fasc,
            form,
            atto_id,
            allegati_ids,
        )
        if selection_error:
            return jsonify({"ok": False, "errore": selection_error}), 400
        try:
            atto_path = str(gestore_fascicoli.percorso_documento(id_fasc, atto_id))
            allegati_busta = _allegati_busta(
                fascicolo,
                gestore_fascicoli,
                id_fasc,
                [item for item in allegati_ids if item != atto_id],
                AllegatoBusta,
            )
            ufficio_deposito = _ufficio_deposito_destinatario(fascicolo)
            codice_ufficio = str(ufficio_deposito.get("codice_ufficio") or "SCONOSCIUTO")
            busta = BustaTelematica(
                DatiBusta(
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
                    valore_causa=_valore_causa_fascicolo(fascicolo),
                )
            )
            pdf_bytes = busta.crea_indice_documenti_pdf()
        except Exception as exc:
            app.logger.exception("Errore indice documenti %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": "Indice documenti non generato. Verifica la selezione e riprova."}), 500
        return send_file(
            _BytesIO(pdf_bytes),
            as_attachment=False,
            download_name=INDICE_DOCUMENTI_FILENAME,
            mimetype="application/pdf",
        )
    @app.route("/fascicoli/<id_fasc>/deposito/invia-pec", methods=["POST"])
    def deposito_invia_pec(id_fasc):
        """Crea la busta telematica e la invia via PEC all'ufficio giudiziario."""
        import json as _json
        import tempfile as _tmp
        import uuid as _uuid
        from datetime import datetime as _dt
        from pct.busta import Allegato as AllegatoBusta
        from pct.busta import BustaTelematica, DatiBusta
        from pct.fascicoli import EsitoDepositoPCT
        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 404
        tipo_atto = form.get("tipo_atto", "ATTO").strip()
        codice_registro = form.get("codice_registro", "RG").strip()
        catalog_entry, catalog_error = _deposito_catalogo_entry(form)
        if catalog_error:
            return jsonify({"ok": False, "package_ready": False, "errore": catalog_error}), 400
        tipo_atto, codice_registro = _deposito_catalogo_apply(catalog_entry, tipo_atto, codice_registro)
        catalog_blocker = _deposito_catalogo_blocker(catalog_entry, require_real_package=True)
        if catalog_blocker:
            return jsonify(
                {
                    "ok": False,
                    "package_ready": False,
                    "requires_guided_completion": True,
                    "errore": catalog_blocker,
                    "next_actions": [
                        "Mantieni la scelta nel catalogo Studio Telematico.",
                        "Completa il generatore ministeriale specifico o usa il flusso corretto per il canale selezionato.",
                    ],
                }
            ), 400
        oggetto = _deposito_oggetto(form, fascicolo)
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
        selection_error = _validate_busta_document_selection(
            fascicolo,
            gestore_fascicoli,
            id_fasc,
            form,
            atto_id,
            allegati_ids,
        )
        if selection_error:
            return jsonify({"ok": False, "errore": selection_error}), 400
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
                    "simulazione": bool(modalita_demo),
                    "id_deposito": id_dep,
                    "pec_dest": nome_commissione,
                    "tipo_atto": tipo_atto,
                    "timestamp": timestamp,
                    "messaggio": "Deposito registrato nello studio.",
                    "validation": {
                        "ok": True,
                        "blockers": 0,
                        "warnings": 0,
                        "issues": [],
                        "channel": "PTT_TRIBUTARIO",
                        "can_prepare_deposit": True,
                    },
                }
            )
        allegati_busta = _allegati_busta(
            fascicolo,
            gestore_fascicoli,
            id_fasc,
            [item for item in allegati_ids if item != atto_id],
            AllegatoBusta,
        )
        ufficio_deposito = _ufficio_deposito_destinatario(fascicolo)
        codice_ufficio = str(ufficio_deposito.get("codice_ufficio") or "SCONOSCIUTO")
        pec_dest = str(ufficio_deposito.get("pec_dest") or "")
        if not pec_dest:
            return jsonify(
                {
                    "ok": False,
                    "errore": f"Indirizzo PEC non trovato per '{fascicolo.tribunale}'. Verifica il tribunale nel fascicolo.",
                }
            ), 400
        prova_senza_invio = form.get("prova_senza_invio", "").strip() == "1"
        simula_invio_pec = form.get("simula_invio_pec", "").strip() == "1"
        controllo_senza_invio = prova_senza_invio or simula_invio_pec
        modalita_demo = simula_invio_pec
        pec_cfg = None
        pec_config_error = ""
        try:
            studio_cfg = get_config_studio().config
            pec_cfg = studio_cfg.pec if studio_cfg else None
            if not pec_cfg or not pec_cfg.indirizzo:
                pec_config_error = "PEC mittente dello studio non configurata."
                pec_cfg = None
            elif not str(getattr(pec_cfg, "smtp_host", "") or "").strip():
                pec_config_error = "Host SMTP PEC dello studio non configurato."
        except Exception:
            pec_config_error = "Configurazione PEC dello studio non leggibile."
            pec_cfg = None
        if pec_config_error and not (simula_invio_pec or prova_senza_invio):
            return jsonify(
                {
                    "ok": False,
                    "package_ready": False,
                    "errore": (
                        f"{pec_config_error} Configura la PEC in Impostazioni prima della prova o dell'invio reale."
                    ),
                    "next_actions": [
                        "Apri Impostazioni > PEC e verifica indirizzo, host SMTP, porta e SSL.",
                        "Ripeti la prova senza invio: l'invio reale non viene simulato automaticamente.",
                    ],
                }
            ), 400
        def _con_avviso_pec_mittente(payload: dict) -> dict:
            return _aggiungi_avviso_pec_mittente(payload, pec_config_error)
        try:
            anagrafica_xml = _anagrafica_xml_se_ricorso(
                tipo_atto=tipo_atto,
                fascicolo=fascicolo,
                get_clienti=get_clienti,
                get_config_studio=get_config_studio,
                operatore=utente.username if utente else "",
            )
        except ValueError as exc:
            return jsonify(
                {
                    "ok": False,
                    "package_ready": False,
                    "errore": str(exc),
                    "next_actions": [
                        "Completa i dati anagrafici indicati prima della firma del DatiAtto.xml.",
                        "Rigenera la prova senza invio: il software deve creare un DatiAtto ministeriale completo.",
                    ],
                    "validation": _validation_summary(validation),
                }
            ), 400
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
            valore_causa=_valore_causa_fascicolo(fascicolo),
            anagrafica_procedimento_xml=anagrafica_xml,
        )
        output_dir = os.getenv("PCT_DEPOSITI_DIR", _tmp.gettempdir())
        requested_busta_id = str(form.get("busta_id", "") or "").strip() or None
        requested_busta_timestamp = str(form.get("busta_timestamp", "") or "").strip() or None
        busta = BustaTelematica(
            dati,
            id_busta=requested_busta_id,
            timestamp=requested_busta_timestamp,
        )
        id_dep = form.get("local_pec_id_deposito", "").strip() or busta.id_busta[:8].upper()
        timestamp = busta.timestamp.isoformat(timespec="seconds")
        oggetto_pec = deposito_pec_subject(
            tipo_atto=tipo_atto,
            numero_rg=numero_rg,
            anno_rg=anno_rg,
            tribunale=fascicolo.tribunale or "",
        )
        documenti_busta = _documenti_busta_nomi(atto_path, allegati_busta, include_indice_busta=True)
        corpo_pec = resolve_deposito_pec_body(form.get("corpo_pec", ""), documenti_busta)
        dati_atto_firmato, signature_payload = _dati_atto_signature_gate(
            form,
            busta,
            id_deposito=id_dep,
            timestamp=timestamp,
            pec_dest=pec_dest,
            tipo_atto=tipo_atto,
            oggetto_pec=oggetto_pec,
            corpo_pec=corpo_pec,
            documenti_busta=documenti_busta,
        )
        if signature_payload is not None:
            signature_status = int(signature_payload.pop("_status", 200))
            return redacted_json_response(signature_payload, signature_status)
        def _compatibility_report(attachment_path: str, busta_audit: dict[str, Any] | None = None) -> dict[str, Any]:
            return _build_compatibility_report(
                id_deposito=id_dep,
                pec_dest=pec_dest,
                oggetto_pec=oggetto_pec,
                corpo_pec=corpo_pec,
                documenti_busta=documenti_busta,
                attachment_path=attachment_path,
                busta_audit=busta_audit or busta.audit_conformita_pst(),
                validation=validation,
                codice_ufficio=codice_ufficio,
                ufficio_nome=fascicolo.tribunale or "",
                tipo_atto=tipo_atto,
                numero_rg=numero_rg,
                anno_rg=anno_rg,
                simulazione_senza_invio=controllo_senza_invio,
            )
        try:
            enc_path = busta.crea_busta(
                output_dir,
                dati_atto_firmato=dati_atto_firmato,
                require_dati_atto_firmato=True,
            )
            busta_audit = busta.audit_conformita_pst()
            compatibility_report = _compatibility_report(enc_path, busta_audit)
        except PSTCifraturaError as exc:
            app.logger.exception("Certificato PST/cifratura busta non completata %s: %s", id_fasc, exc)
            guided_response = _guided_transport_completion_response(
                busta=busta,
                id_deposito=id_dep,
                timestamp=timestamp,
                pec_dest=pec_dest,
                tipo_atto=tipo_atto,
                oggetto_pec=oggetto_pec,
                corpo_pec=corpo_pec,
                documenti_busta=documenti_busta,
                attachment_path=getattr(busta, "_last_atto_msg_path", "") or "",
                validation=validation,
            )
            payload_guidato = (
                _con_avviso_pec_mittente(guided_response)
                if guided_response
                else _con_avviso_pec_mittente(
                    {
                        "ok": False,
                        "requires_guided_completion": True,
                        "package_ready": True,
                        "errore": "Invio diretto sospeso: certificato PST non disponibile.",
                        "message": (
                            "Il software ha preparato il pacchetto di controllo, ma non registra un deposito come valido "
                            "finché Atto.msg non viene cifrato in Atto.enc con il certificato PST dell'ufficio."
                        ),
                        "next_actions": [
                            f"Recupera o collega il certificato pubblico PST .cer dell'ufficio {codice_ufficio}.",
                            "Genera Atto.enc ministeriale prima dell'invio reale.",
                        ],
                        "documenti_busta": documenti_busta,
                        "corpo_pec": corpo_pec,
                    }
                )
            )
            guided_audit = payload_guidato.get("busta_audit") if isinstance(payload_guidato.get("busta_audit"), dict) else busta.audit_conformita_pst()
            payload_guidato.setdefault("busta_audit", guided_audit)
            payload_guidato["compatibility_report"] = _compatibility_report(
                getattr(busta, "_last_atto_msg_path", "") or "",
                guided_audit,
            )
            return redacted_json_response(payload_guidato, 200 if controllo_senza_invio else 409)
        except Exception as exc:
            app.logger.exception("Errore creazione busta %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": "Creazione busta non completata. Verifica documenti e fascicolo."}), 500
        guided_response = _guided_transport_completion_response(
            busta=busta,
            id_deposito=id_dep,
            timestamp=timestamp,
            pec_dest=pec_dest,
            tipo_atto=tipo_atto,
            oggetto_pec=oggetto_pec,
            corpo_pec=corpo_pec,
            documenti_busta=documenti_busta,
            attachment_path=enc_path,
            validation=validation,
        )
        if guided_response:
            guided_payload = _con_avviso_pec_mittente(guided_response)
            guided_payload.setdefault("busta_audit", busta_audit)
            guided_payload["compatibility_report"] = compatibility_report
            return redacted_json_response(
                guided_payload,
                200 if controllo_senza_invio else 409,
            )
        if prova_senza_invio:
            prova_payload = local_pec_required_response(
                pec_cfg=pec_cfg,
                pec_dest=pec_dest,
                tipo_atto=tipo_atto,
                id_deposito=id_dep,
                timestamp=timestamp,
                oggetto_pec=oggetto_pec,
                attachment_path=enc_path,
                validation=validation,
                documenti=documenti_busta,
                corpo_pec=corpo_pec,
                busta_audit=busta_audit,
            )
            prova_payload["compatibility_report"] = compatibility_report
            prova_payload["messaggio"] = (
                "Prova deposito preparata: busta, indice, destinatario e testo PEC sono pronti per il controllo. "
                "Nessun invio PEC reale è stato eseguito."
            )
            _con_avviso_pec_mittente(prova_payload)
            return redacted_json_response(prova_payload, 200)
        if simula_invio_pec:
            sim_payload = _build_simulazione_pec_payload(
                pec_cfg=pec_cfg,
                pec_dest=pec_dest,
                tipo_atto=tipo_atto,
                id_deposito=id_dep,
                timestamp=timestamp,
                oggetto_pec=oggetto_pec,
                attachment_path=enc_path,
                validation=validation,
                documenti=documenti_busta,
                corpo_pec=corpo_pec,
                busta_audit=busta_audit,
                compatibility_report=compatibility_report,
                pec_config_error=pec_config_error,
            )
            try:
                _registra_prova_senza_invio_pec(
                    fascicolo=fascicolo,
                    gestore_fascicoli=gestore_fascicoli,
                    atto_id=atto_id,
                    allegati_ids=allegati_ids,
                    id_deposito=id_dep,
                    timestamp=timestamp,
                    tipo_atto=tipo_atto,
                    pec_dest=pec_dest,
                    note=note,
                    username=utente.username if utente else "",
                    audit=audit,
                    sync_pubblica=sync_pubblica,
                    id_fascicolo=id_fasc,
                )
            except Exception as exc:
                app.logger.exception("Errore salvataggio prova senza invio PEC %s: %s", id_fasc, exc)
                sim_payload["avviso"] = "La prova è stata generata, ma il salvataggio nel fascicolo non è stato completato."
            return redacted_json_response(sim_payload, 200)
        if form.get("local_pec_confirmed") == "1":
            try:
                ris = local_pec_confirmation_result(form.get("local_pec_message_id", ""))
            except ValueError as exc:
                app.logger.warning("Conferma Local Signer non valida per deposito %s: %s", id_dep, exc)
                return jsonify({"ok": False, "errore": "Conferma Local Signer non valida. Ripeti l'invio dal PC locale."}), 400
            app.logger.info("Deposito %s confermato da invio PEC Local Signer", id_dep)
        else:
            # Il deposito PCT/SIGP invia sempre dal PC dell'avvocato tramite
            # Local Signer, anche quando la UI e' aperta dal server pubblico.
            local_payload = local_pec_required_response(
                pec_cfg=pec_cfg,
                pec_dest=pec_dest,
                tipo_atto=tipo_atto,
                id_deposito=id_dep,
                timestamp=timestamp,
                oggetto_pec=oggetto_pec,
                attachment_path=enc_path,
                validation=validation,
                documenti=documenti_busta,
                corpo_pec=corpo_pec,
                busta_audit=busta_audit,
            )
            local_payload["compatibility_report"] = compatibility_report
            return redacted_json_response(local_payload, 200)
        try:
            from datetime import datetime as _dtnow
            from pct.fascicoli import AttivitaProcessuale, EsitoAttivita, TIPO_ATTO_LABEL, _tipo_attivita_da_tipo_atto
            atto_doc = next((doc for doc in fascicolo.documenti if doc.id == atto_id), None)
            tutti_ids = [atto_id] + [aid for aid in allegati_ids if aid != atto_id]
            esito = EsitoDepositoPCT(
                id=id_dep,
                timestamp=timestamp,
                stato="INVIATO",
                tipo_atto=tipo_atto,
                pec_destinatario=pec_dest,
                messaggio=f"Busta {id_dep} inviata via PEC a {pec_dest}. Message-ID: {ris.get('message_id', '')}",
                note=note,
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
                    "demo": False,
                    "simulazione": False,
                    "avviso": "Busta inviata, ma il salvataggio dell'esito non è stato completato.",
                    "id_deposito": id_dep,
                    "pec_dest": pec_dest,
                    "tipo_atto": tipo_atto,
                }
            )
        return jsonify(
            {
                "ok": True,
                "demo": False,
                "simulazione": False,
                "id_deposito": id_dep,
                "pec_dest": pec_dest,
                "tipo_atto": tipo_atto,
                "timestamp": timestamp,
                "message_id": ris.get("message_id", ""),
                "messaggio": "Deposito inviato via PEC e registrato nel fascicolo.",
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
        ufficio_deposito = _ufficio_deposito_destinatario(fascicolo)
        pec_tribunale = str(ufficio_deposito.get("pec_dest") or "")
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
