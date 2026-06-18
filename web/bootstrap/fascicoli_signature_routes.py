"""Signature and compliance routes extracted from the fascicoli monolith."""

from __future__ import annotations

import io
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, request, send_file, url_for

from pct.document_signature_state import document_has_real_digital_signature
from web.services.fascicoli_signature_pdf import attestazione_conformita_pdf
from web.services.fascicoli_signature_options import (
    messaggio_firma_pubblico as _messaggio_firma_pubblico,
    metadata_firma_cades as _metadata_firma_cades,
    metadata_firma_pades as _metadata_firma_pades,
    normalizza_data_ora_firma_visibile,
    nota_con_firma_visibile,
    resolve_pkcs11_runtime_config,
    salva_documento_firmato_compat as _salva_documento_firmato_compat,
)


def register_fascicoli_signature_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_config_studio: Callable[[], Any],
    decrypt_doc: Callable[[bytes], bytes],
    encrypt_doc: Callable[[bytes], bytes],
    salva_documento_firmato_resiliente: Callable[..., list[str]],
    audit_and_sync_best_effort: Callable[..., list[str]],
    signature_storage_error_message: Callable[[Exception], str],
    normalizza_modalita_firma_visibile: Callable[[str], str],
    luogo_timbro_firma_visibile: Callable[[], str],
    audit: Callable[..., None],
) -> None:
    """Register PKCS#11, uploaded-signature, and attestazione routes."""

    @app.route("/api/firma/pkcs11/status", methods=["GET"])
    def api_pkcs11_status():
        try:
            from pct.firma_pkcs11 import libreria_disponibile, lista_token

            cfg_studio = get_config_studio().config
            firma_cfg = cfg_studio.firma if cfg_studio else None
            lib_path = (
                getattr(firma_cfg, "pkcs11_library", "") or libreria_disponibile()
                if firma_cfg
                else libreria_disponibile()
            )
            if not lib_path:
                return jsonify(
                    {
                        "disponibile": False,
                        "libreria": None,
                        "token": [],
                        "messaggio": (
                            "Nessuna libreria PKCS#11 trovata. Installare opensc e pcscd oppure "
                            "specificare il percorso in Impostazioni → Firma Digitale → Token PKCS#11."
                        ),
                    }
                )

            token_list = lista_token(lib_path)
            return jsonify(
                {
                    "disponibile": True,
                    "libreria": lib_path,
                    "token": [token.as_dict() for token in token_list],
                    "messaggio": (
                        f"{len(token_list)} token rilevato/i."
                        if token_list
                        else "Libreria PKCS#11 disponibile ma nessun token inserito. Inserire smart card/token o collegare il lettore."
                    ),
                }
            )
        except Exception as exc:
            app.logger.exception("Errore api_pkcs11_status: %s", exc)
            return jsonify(
                {
                    "disponibile": False,
                    "libreria": None,
                    "token": [],
                    "messaggio": "Stato firma digitale non disponibile. Verifica il dispositivo e riprova.",
                }
            )

    @app.route("/api/firma/pkcs11/firma-documento", methods=["POST"])
    def api_pkcs11_firma_documento():
        try:
            from pct.firma import busta_cades_valida, crea_signer_da_config

            data = request.get_json(force=True) or {}
            id_fasc = str(data.get("fascicolo_id") or "").strip()
            id_doc = str(data.get("documento_id") or "").strip()
            pin = data.get("pin", "")
            formato = str(data.get("formato") or "cades").strip().lower()
            cfg_firma = get_config_studio().config.firma
            visible_signature_mode = normalizza_modalita_firma_visibile(
                str(data.get("visible_signature_mode") or getattr(cfg_firma, "visible_signature_mode", "laterale")).strip()
            )
            visible_signature_place = str(data.get("visible_signature_place") or luogo_timbro_firma_visibile()).strip()
            visible_signature_datetime_mode = normalizza_data_ora_firma_visibile(
                data.get("visible_signature_datetime_mode")
            )

            if not id_fasc or not id_doc:
                return jsonify({"ok": False, "messaggio": "fascicolo_id e documento_id obbligatori."}), 400
            if not pin:
                return jsonify({"ok": False, "messaggio": "PIN obbligatorio per la firma in-device."}), 400

            try:
                backend_firma = cfg_firma.backend_firma_effettivo
            except (FileNotFoundError, ValueError) as exc:
                app.logger.warning("Configurazione backend firma non valida: %s", exc)
                return jsonify({"ok": False, "messaggio": "Configurazione firma digitale da verificare."}), 400
            if backend_firma != "pkcs11":
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": "La firma in-device è disponibile solo quando il backend selezionato è Token PKCS#11.",
                    }
                ), 400
            try:
                formato = cfg_firma.valida_formato_firma(formato)
            except ValueError as exc:
                app.logger.warning("Formato firma non valido: %s", exc)
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": _messaggio_firma_pubblico(
                            exc,
                            "Formato firma non supportato per questo dispositivo.",
                        ),
                    }
                ), 400
            if formato != "cades":
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": "La firma PKCS#11 supporta solo CAdES (.p7m). Per PAdES usare P12/PEM.",
                    }
                ), 400

            utente = g.utente_corrente
            gestore_fascicoli = get_fascicoli()
            fascicolo = gestore_fascicoli.get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "messaggio": "Fascicolo non trovato."}), 404
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            if not documento:
                return jsonify({"ok": False, "messaggio": "Documento non trovato."}), 404
            if documento.firmato_digitalmente:
                return jsonify({"ok": True, "nome_firmato": documento.nome, "messaggio": "Documento già firmato digitalmente."})

            doc_path = gestore_fascicoli.percorso_documento(id_fasc, id_doc)
            if not doc_path or not doc_path.exists():
                return jsonify({"ok": False, "messaggio": "File documento non trovato su disco."}), 404

            with open(doc_path, "rb") as fh:
                contenuto = fh.read()

            cfg_firma_runtime = resolve_pkcs11_runtime_config(cfg_firma, data.get("slot_id"))
            with crea_signer_da_config(cfg_firma_runtime, pin=pin) as firma:
                stato_cert = firma.verifica_scadenza()
                if stato_cert["scaduto"]:
                    return jsonify({"ok": False, "messaggio": stato_cert["messaggio"]})

                output_path = str(doc_path) + ".p7m"
                _salva_documento_firmato_compat(
                    firma,
                    contenuto,
                    str(doc_path),
                    formato="cades",
                    visible_signature_mode=visible_signature_mode,
                    visible_signature_place=visible_signature_place,
                    visible_signature_datetime_mode=visible_signature_datetime_mode,
                )
                firmato_path = output_path if output_path.endswith(".p7m") else str(doc_path) + ".p7m"
                intestatario = firma.intestatario
                scadenza_str = stato_cert["scadenza"]

            nome_firmato = documento.nome if documento.nome.endswith(".p7m") else f"{documento.nome}.p7m"
            if not os.path.exists(firmato_path):
                return jsonify({"ok": False, "messaggio": "Il file firmato non è stato generato dal token PKCS#11."}), 500

            contenuto_firmato = Path(firmato_path).read_bytes()
            if not busta_cades_valida(contenuto_firmato):
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": "Il token ha restituito un file .p7m non valido. Aggiorna il Local Signer e ripeti la firma.",
                    }
                ), 500

            avvisi_storage = salva_documento_firmato_resiliente(
                gf=gestore_fascicoli,
                id_fasc=id_fasc,
                id_doc=id_doc,
                nome_file=nome_firmato,
                contenuto=encrypt_doc(contenuto_firmato),
                caricato_da=utente.username if utente else "",
                note=nota_con_firma_visibile(
                    "Versione firmata per deposito",
                    visible_signature_mode,
                    visible_signature_place,
                    visible_signature_datetime_mode,
                ),
            )
            gestore_fascicoli.segna_firmato(
                id_fasc,
                id_doc,
                signature_metadata=_metadata_firma_cades(nome_firmato, source="pkcs11"),
            )
            try:
                Path(firmato_path).unlink(missing_ok=True)
            except Exception:
                pass

            avvisi_operativi = audit_and_sync_best_effort(
                audit_azione="firma.pkcs11",
                audit_risorsa_tipo="documento",
                audit_risorsa_id=id_doc,
                audit_dettagli=f"Firmato via PKCS#11 da {intestatario} — {nome_firmato}",
                sync_tipo="modifica",
                sync_modulo="fascicoli",
                sync_id_risorsa=id_fasc,
            )
            warning_codes = avvisi_storage + avvisi_operativi

            return jsonify(
                {
                    "ok": True,
                    "nome_firmato": nome_firmato,
                    "intestatario": intestatario,
                    "scadenza": scadenza_str,
                    "avviso_scadenza": stato_cert.get("avviso_imminente", False),
                    "messaggio": f"Documento firmato con successo da {intestatario}. "
                    + (stato_cert["messaggio"] if stato_cert.get("avviso_imminente") else ""),
                    "warning": bool(warning_codes),
                    "warning_codes": warning_codes,
                    "visible_signature_mode": visible_signature_mode,
                    "visible_signature_datetime_mode": visible_signature_datetime_mode,
                }
            )
        except Exception as exc:
            app.logger.exception("Errore api_pkcs11_firma_documento: %s", exc)
            return jsonify({"ok": False, "messaggio": signature_storage_error_message(exc)})

    @app.route("/api/firma/pkcs11/firma-documenti-batch", methods=["POST"])
    def api_pkcs11_firma_documenti_batch():
        try:
            from datetime import datetime

            from pct.firma import busta_cades_valida, crea_signer_da_config

            data = request.get_json(force=True) or {}
            id_fasc = str(data.get("fascicolo_id") or "").strip()
            documento_ids = [str(item).strip() for item in (data.get("documento_ids") or []) if str(item).strip()]
            pin = data.get("pin", "")
            formato = str(data.get("formato") or "cades").strip().lower()
            cfg_firma = get_config_studio().config.firma
            visible_signature_mode = normalizza_modalita_firma_visibile(
                str(data.get("visible_signature_mode") or getattr(cfg_firma, "visible_signature_mode", "laterale")).strip()
            )
            visible_signature_place = str(data.get("visible_signature_place") or luogo_timbro_firma_visibile()).strip()
            visible_signature_datetime_mode = normalizza_data_ora_firma_visibile(
                data.get("visible_signature_datetime_mode")
            )

            if not id_fasc or not documento_ids:
                return jsonify({"ok": False, "messaggio": "fascicolo_id e documento_ids obbligatori."}), 400
            if not pin:
                return jsonify({"ok": False, "messaggio": "PIN obbligatorio per la firma batch in-device."}), 400

            try:
                backend_firma = cfg_firma.backend_firma_effettivo
            except (FileNotFoundError, ValueError) as exc:
                app.logger.warning("Configurazione backend firma batch non valida: %s", exc)
                return jsonify({"ok": False, "messaggio": "Configurazione firma digitale da verificare."}), 400
            if backend_firma != "pkcs11":
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": "La firma batch in-device è disponibile solo quando il backend selezionato è Token PKCS#11.",
                    }
                ), 400
            try:
                formato = cfg_firma.valida_formato_firma(formato)
            except ValueError as exc:
                app.logger.warning("Formato firma batch non valido: %s", exc)
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": _messaggio_firma_pubblico(
                            exc,
                            "Formato firma non supportato per questo dispositivo.",
                        ),
                    }
                ), 400
            if formato != "cades":
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": "La firma PKCS#11 supporta solo CAdES (.p7m). Per PAdES usare P12/PEM.",
                    }
                ), 400

            utente = g.utente_corrente
            gestore_fascicoli = get_fascicoli()
            fascicolo = gestore_fascicoli.get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "messaggio": "Fascicolo non trovato."}), 404

            cfg_firma_runtime = resolve_pkcs11_runtime_config(cfg_firma, data.get("slot_id"))
            risultati = []
            firmati = 0
            saltati = 0
            errori = 0
            warning_codes_batch: set[str] = set()

            with crea_signer_da_config(cfg_firma_runtime, pin=pin) as firma:
                stato_cert = firma.verifica_scadenza()
                if stato_cert["scaduto"]:
                    return jsonify({"ok": False, "messaggio": stato_cert["messaggio"]}), 400

                for id_doc in documento_ids:
                    documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
                    if not documento:
                        risultati.append({"ok": False, "documento_id": id_doc, "messaggio": "Documento non trovato."})
                        errori += 1
                        continue
                    if documento.firmato_digitalmente:
                        risultati.append(
                            {
                                "ok": True,
                                "documento_id": id_doc,
                                "nome_firmato": documento.nome,
                                "saltato": True,
                                "messaggio": "Documento già firmato digitalmente.",
                            }
                        )
                        saltati += 1
                        continue

                    doc_path = gestore_fascicoli.percorso_documento(id_fasc, id_doc)
                    if not doc_path or not doc_path.exists():
                        risultati.append({"ok": False, "documento_id": id_doc, "messaggio": "File documento non trovato su disco."})
                        errori += 1
                        continue

                    with open(doc_path, "rb") as fh:
                        contenuto = fh.read()

                    _salva_documento_firmato_compat(
                        firma,
                        contenuto,
                        str(doc_path),
                        formato="cades",
                        visible_signature_mode=visible_signature_mode,
                        visible_signature_place=visible_signature_place,
                        visible_signature_datetime_mode=visible_signature_datetime_mode,
                    )
                    firmato_path = str(doc_path) + ".p7m"
                    nome_firmato = documento.nome if documento.nome.endswith(".p7m") else f"{documento.nome}.p7m"

                    if not os.path.exists(firmato_path):
                        risultati.append({"ok": False, "documento_id": id_doc, "messaggio": "Il file .p7m firmato non è stato generato."})
                        errori += 1
                        continue

                    contenuto_firmato = Path(firmato_path).read_bytes()
                    if not busta_cades_valida(contenuto_firmato):
                        risultati.append(
                            {
                                "ok": False,
                                "documento_id": id_doc,
                                "messaggio": "Il file .p7m generato non contiene una firma CAdES valida. Aggiorna il Local Signer e ripeti la firma.",
                            }
                        )
                        errori += 1
                        try:
                            Path(firmato_path).unlink(missing_ok=True)
                        except Exception:
                            pass
                        continue

                    avvisi_storage = salva_documento_firmato_resiliente(
                        gf=gestore_fascicoli,
                        id_fasc=id_fasc,
                        id_doc=id_doc,
                        nome_file=nome_firmato,
                        contenuto=encrypt_doc(contenuto_firmato),
                        caricato_da=utente.username if utente else "",
                        note=nota_con_firma_visibile(
                            "Versione firmata per deposito",
                            visible_signature_mode,
                            visible_signature_place,
                            visible_signature_datetime_mode,
                        ),
                    )
                    gestore_fascicoli.segna_firmato(
                        id_fasc,
                        id_doc,
                        signature_metadata=_metadata_firma_cades(nome_firmato, source="pkcs11.batch"),
                    )
                    try:
                        Path(firmato_path).unlink(missing_ok=True)
                    except Exception:
                        pass

                    warning_codes_batch.update(avvisi_storage)
                    risultati.append(
                        {
                            "ok": True,
                            "documento_id": id_doc,
                            "nome_firmato": nome_firmato,
                            "warning": bool(avvisi_storage),
                            "warning_codes": avvisi_storage,
                            "messaggio": "Documento firmato con successo.",
                        }
                    )
                    firmati += 1

            fascicolo.modificato_il = datetime.now().isoformat()
            gestore_fascicoli._salva()
            avvisi_operativi = audit_and_sync_best_effort(
                audit_azione="firma.pkcs11.batch",
                audit_risorsa_tipo="fascicolo",
                audit_risorsa_id=id_fasc,
                audit_dettagli=f"Firmati {firmati} documenti via PKCS#11 nel fascicolo {id_fasc}",
                sync_tipo="modifica",
                sync_modulo="fascicoli",
                sync_id_risorsa=id_fasc,
            )
            warning_codes = sorted(warning_codes_batch) + avvisi_operativi

            return jsonify(
                {
                    "ok": errori == 0,
                    "firmati": firmati,
                    "saltati": saltati,
                    "errori": errori,
                    "intestatario": getattr(firma, "intestatario", ""),
                    "scadenza": stato_cert.get("scadenza", ""),
                    "avviso_scadenza": stato_cert.get("avviso_imminente", False),
                    "risultati": risultati,
                    "warning": bool(warning_codes),
                    "warning_codes": warning_codes,
                    "visible_signature_mode": visible_signature_mode,
                    "visible_signature_datetime_mode": visible_signature_datetime_mode,
                    "messaggio": f"Firma batch completata: {firmati} firmati, {saltati} già firmati, {errori} errori.",
                }
            )
        except Exception as exc:
            app.logger.exception("Errore api_pkcs11_firma_documenti_batch: %s", exc)
            return jsonify({"ok": False, "messaggio": signature_storage_error_message(exc)})

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/firma", methods=["GET", "POST"])
    def firma_documento(id_fasc, id_doc):
        if request.method == "GET":
            from web.blueprints.react_shell import render_react_shell_response

            return render_react_shell_response(f"fascicoli/{id_fasc}/documenti/{id_doc}/firma")

        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        richiesta_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        def _chiudi_risposta(ok: bool, messaggio: str, categoria: str, status: int = 200, **extra):
            if richiesta_ajax:
                payload = {"ok": ok, "messaggio": messaggio}
                payload.update(extra)
                return jsonify(payload), status
            flash(messaggio, categoria)
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        try:
            fascicolo_corrente = gestore_fascicoli.get(id_fasc)
            documento_corrente = next((doc for doc in getattr(fascicolo_corrente, "documenti", []) if doc.id == id_doc), None)
            if documento_corrente is None:
                raise KeyError("Documento non trovato.")
            nome_corrente = str(getattr(documento_corrente, "nome", "") or "")
            gia_firmato = document_has_real_digital_signature(documento_corrente, nome_corrente)
            conferma_rifirma = str(request.form.get("confirm_resign") or "").strip().lower() in {
                "1",
                "true",
                "si",
                "sì",
                "yes",
            }
            if gia_firmato and not conferma_rifirma:
                return _chiudi_risposta(
                    False,
                    (
                        "Attenzione: documento già firmato. Se continui rischi di corrompere il file "
                        "o di creare una versione firmata non valida. Conferma esplicitamente la nuova firma "
                        "solo se devi sostituire consapevolmente il file firmato."
                    ),
                    "warning",
                    status=409,
                    already_signed=True,
                    requires_confirm_resign=True,
                )

            signature_metadata: dict[str, Any] | None = None
            if "file" in request.files and request.files["file"].filename:
                from pct.firma import analizza_firma_documento, busta_cades_valida

                file = request.files["file"]
                cfg_firma = get_config_studio().config.firma
                visible_signature_mode = normalizza_modalita_firma_visibile(
                    str(request.form.get("visible_signature_mode") or getattr(cfg_firma, "visible_signature_mode", "laterale")).strip()
                )
                visible_signature_place = str(request.form.get("visible_signature_place") or luogo_timbro_firma_visibile()).strip()
                visible_signature_datetime_mode = normalizza_data_ora_firma_visibile(
                    request.form.get("visible_signature_datetime_mode")
                )
                payload_firmato = file.read()
                est = Path(file.filename or "").suffix.lower()
                if est == ".pdf":
                    formato_file = "pades"
                elif est in {".p7m", ".sig", ".pkcs7"}:
                    formato_file = "cades"
                else:
                    raise ValueError(
                        "Formato file firmato non supportato. Usa un file .p7m (CAdES) oppure .pdf firmato (PAdES)."
                    )
                if getattr(cfg_firma, "configurato", False):
                    cfg_firma.valida_formato_firma(formato_file)
                if formato_file == "cades":
                    if not busta_cades_valida(payload_firmato):
                        raise ValueError(
                            "Il file .p7m caricato non contiene una firma CAdES valida. Non caricare PDF rinominati in .p7m: verifica prima il file in ArubaSign o Dike."
                        )
                    signature_metadata = _metadata_firma_cades(file.filename, source="upload")
                else:
                    firme = analizza_firma_documento(payload_firmato, file.filename)
                    if not firme:
                        raise ValueError(
                            "Il PDF caricato resta .PDF ma non contiene una firma PAdES interna verificabile. Carica un .pdf.p7m CAdES oppure un PDF PAdES valido."
                        )
                    signature_metadata = _metadata_firma_pades(file.filename, firme, source="upload")
                note = nota_con_firma_visibile(
                    request.form.get("note", "Versione firmata per deposito").strip(),
                    visible_signature_mode,
                    visible_signature_place,
                    visible_signature_datetime_mode,
                )
                avvisi_storage = salva_documento_firmato_resiliente(
                    gf=gestore_fascicoli,
                    id_fasc=id_fasc,
                    id_doc=id_doc,
                    nome_file=file.filename,
                    contenuto=encrypt_doc(payload_firmato),
                    caricato_da=utente.username if utente else "",
                    note=note,
                )
            else:
                if gia_firmato and conferma_rifirma:
                    return _chiudi_risposta(
                        True,
                        f"Documento '{documento_corrente.nome}' già firmato: nessuna nuova versione è stata salvata senza file firmato.",
                        "success",
                        nome_firmato=documento_corrente.nome,
                        already_signed=True,
                    )
                raise ValueError(
                    "Per segnare un documento come firmato devi caricare un .pdf.p7m CAdES valido oppure un PDF con firma PAdES interna verificabile."
                )

            documento = gestore_fascicoli.segna_firmato(
                id_fasc,
                id_doc,
                signature_metadata=signature_metadata,
            )
            avvisi_operativi = audit_and_sync_best_effort(
                audit_azione="fascicoli.documento.firma",
                audit_risorsa_tipo="fascicolo",
                audit_risorsa_id=id_fasc,
                audit_dettagli=f"doc {id_doc} — {documento.nome}",
                sync_tipo="modifica",
                sync_modulo="fascicoli",
                sync_id_risorsa=id_fasc,
            )
            warning_codes = avvisi_storage + avvisi_operativi
            return _chiudi_risposta(
                True,
                f"Documento '{documento.nome}' salvato come firmato per deposito con prova tecnica.",
                "success",
                nome_firmato=documento.nome,
                warning=bool(warning_codes),
                warning_codes=warning_codes,
            )
        except (ValueError, KeyError) as exc:
            app.logger.warning("Firma documento non valida: %s", exc)
            return _chiudi_risposta(
                False,
                _messaggio_firma_pubblico(exc, "Firma caricata non valida o non verificabile."),
                "danger",
                status=400,
            )
        except Exception as exc:
            app.logger.exception("Errore firma_documento(%s, %s): %s", id_fasc, id_doc, exc)
            return _chiudi_risposta(False, signature_storage_error_message(exc), "danger", status=500)

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/attestazione", methods=["POST"])
    def attestazione_conformita(id_fasc, id_doc):
        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        try:
            percorso = gestore_fascicoli.percorso_documento(id_fasc, id_doc)
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            data_raw = decrypt_doc(percorso.read_bytes())
            nome_avvocato = (utente.nome_completo if hasattr(utente, "nome_completo") else utente.username) if utente else "Avvocato"
            data_oggi = __import__("datetime").date.today().strftime("%d/%m/%Y")
            testo = (
                "Copia conforme all'originale\n"
                "ai sensi dell'art. 22, co. 2, D.Lgs. 82/2005 (CAD)\n"
                f"Avv. {nome_avvocato} — {data_oggi}"
            )
            attested = attestazione_conformita_pdf(data_raw, testo)
            audit("fascicoli.documento.attestazione", "fascicolo", id_fasc, dettagli=f"doc {id_doc} — {documento.nome}")
            nome_out = documento.nome.replace(".pdf", "_conf.pdf") if documento.nome.endswith(".pdf") else documento.nome + "_conf.pdf"
            return send_file(io.BytesIO(attested), mimetype="application/pdf", as_attachment=True, download_name=nome_out)
        except (KeyError, StopIteration, ValueError) as exc:
            app.logger.warning("Attestazione documento non valida: %s", exc)
            flash("Attestazione non generata. Verifica documento e fascicolo.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
