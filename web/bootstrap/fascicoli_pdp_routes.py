"""PDP Penale fascicoli routes extracted from web.app."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, redirect, render_template, request, url_for

from pct.fascicoli import TipoDocumento
from pct.pdp_penale_workflow import pdp_penale_estrai_password, pdp_penale_estrai_scadenza_download


def register_fascicoli_pdp_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_pdp_penale: Callable[[], Any],
    get_config_studio: Callable[[], Any],
    audit: Callable[..., None],
    sync_pubblica: Callable[..., None],
    require_pdp_penale_fascicolo: Callable[..., Any],
    require_pdp_penale_case: Callable[..., dict[str, Any]],
    pdp_penale_build_workspace: Callable[..., dict[str, Any]],
    pdp_penale_case_defaults: Callable[..., dict[str, Any]],
    pdp_penale_int: Callable[..., int],
    pdp_penale_float: Callable[..., float],
    pdp_penale_bool: Callable[..., bool],
    pdp_penale_request_reference: Callable[..., str],
    pdp_penale_primary_access_request: Callable[..., dict[str, Any]],
    pdp_penale_access_status_from_request_status: Callable[..., str],
    pdp_penale_local_documents: Callable[..., list[dict[str, Any]]],
    pdp_penale_module_documents_enriched: Callable[..., list[dict[str, Any]]],
    pdp_penale_generate_request_pdf: Callable[..., bytes],
    pdp_penale_find_case_local_document: Callable[..., Any],
    pdp_penale_sync_case_mailbox: Callable[..., dict[str, Any]],
    pdp_penale_import_download_items: Callable[..., dict[str, Any]],
    pdp_penale_status_label: Callable[..., str],
    decrypt_doc: Callable[[bytes], bytes],
    resolve_ufficio_destinatario: Callable[..., dict[str, Any] | None],
    polis_demo_mode: Callable[[], bool],
    salva_documento_fascicolo: Callable[..., Any],
    espandi_file_importato_portale: Callable[..., list[dict[str, Any]]],
    pst_import_dir_for_fascicolo: Callable[..., Any],
    leggi_staging_documenti_portale: Callable[..., tuple[list[dict[str, Any]], Any]],
    archivia_staging_documenti_portale: Callable[..., str],
) -> None:
    """Register the PDP Penale workspace routes."""

    @app.route("/fascicoli/<id_fasc>/penale/pdp")
    def pdp_penale_workspace(id_fasc: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            cliente = get_clienti().get(fascicolo.id_cliente) if fascicolo.id_cliente else None
            workspace = pdp_penale_build_workspace(fascicolo, cliente)
            return render_template(
                "fascicoli/pdp_penale.html",
                fascicolo=fascicolo,
                cliente=cliente,
                workspace=workspace,
                oggi=date.today(),
            )
        except Exception as exc:
            app.logger.exception("Errore pdp_penale_workspace(%s): %s", id_fasc, exc)
            flash(str(exc), "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case", methods=["POST"])
    def pdp_penale_save_case(id_fasc: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            cliente = get_clienti().get(fascicolo.id_cliente) if fascicolo.id_cliente else None
            repo = get_pdp_penale()
            defaults = pdp_penale_case_defaults(fascicolo, cliente)
            form = request.form
            case_id = str(form.get("case_id") or "").strip()
            payload = {
                "practice_id": fascicolo.id,
                "minister_case_ref": str(
                    form.get("minister_case_ref") or defaults["minister_case_ref"]
                ).strip(),
                "office_name": str(form.get("office_name") or defaults["office_name"]).strip(),
                "office_type": str(form.get("office_type") or defaults["office_type"]).strip(),
                "district": str(form.get("district") or defaults["district"]).strip(),
                "register_type": str(form.get("register_type") or defaults["register_type"]).strip()
                or "RGNR",
                "register_number": str(
                    form.get("register_number") or defaults["register_number"]
                ).strip(),
                "register_year": pdp_penale_int(
                    form.get("register_year"), defaults["register_year"]
                ),
                "proceeding_type": str(
                    form.get("proceeding_type") or defaults["proceeding_type"]
                ).strip(),
                "prosecutor_name": str(form.get("prosecutor_name") or "").strip(),
                "judge_name": str(form.get("judge_name") or defaults["judge_name"]).strip(),
                "chamber_section": str(
                    form.get("chamber_section") or defaults["chamber_section"]
                ).strip(),
                "assisted_party_name": str(
                    form.get("assisted_party_name") or defaults["assisted_party_name"]
                ).strip(),
                "assisted_party_cf": str(
                    form.get("assisted_party_cf") or defaults["assisted_party_cf"]
                )
                .strip()
                .upper(),
                "defense_counsel_name": str(
                    form.get("defense_counsel_name") or defaults["defense_counsel_name"]
                ).strip(),
                "defense_counsel_cf": str(
                    form.get("defense_counsel_cf") or defaults["defense_counsel_cf"]
                )
                .strip()
                .upper(),
                "nomination_status": str(form.get("nomination_status") or "missing").strip(),
                "access_status": str(form.get("access_status") or "draft").strip(),
                "import_status": str(form.get("import_status") or "not_started").strip(),
                "current_ministry_status": str(form.get("current_ministry_status") or "").strip()
                or None,
                "download_available_until": str(
                    form.get("download_available_until") or ""
                ).strip()
                or None,
                "notes": str(form.get("notes") or "").strip() or None,
            }
            required = {
                "Ufficio": payload["office_name"],
                "Numero procedimento": payload["register_number"],
                "Assistito": payload["assisted_party_name"],
                "Difensore": payload["defense_counsel_name"],
                "Codice fiscale difensore": payload["defense_counsel_cf"],
            }
            missing = [label for label, value in required.items() if not str(value or "").strip()]
            if missing:
                raise ValueError("Campi obbligatori mancanti: " + ", ".join(missing))

            if case_id:
                require_pdp_penale_case(repo, case_id, fascicolo.id)
                case = repo.update_case(case_id, **payload)
                event_type = "case_updated"
                title = "Fascicolo ministeriale PDP aggiornato"
                flash("Fascicolo ministeriale PDP aggiornato.", "success")
            else:
                case = repo.create_case(**payload)
                event_type = "case_created"
                title = "Fascicolo ministeriale PDP creato"
                flash("Fascicolo ministeriale PDP creato.", "success")

            repo.add_event(
                str(case["id"]),
                event_type=event_type,
                event_source="user",
                title=title,
                description=(
                    f"{payload['office_name']} - "
                    f"{payload['register_type']} {payload['register_number']}/{payload['register_year']}"
                ),
                payload_json={
                    "nomination_status": payload["nomination_status"],
                    "access_status": payload["access_status"],
                    "current_ministry_status": payload["current_ministry_status"] or "",
                },
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            audit(
                "fascicoli.pdp_penale.case",
                "fascicolo",
                id_fasc,
                dettagli=f"{title}: {case['id']}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case["id"]))
        except Exception as exc:
            app.logger.exception("Errore pdp_penale_save_case(%s): %s", id_fasc, exc)
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case/<case_id>/document-link", methods=["POST"])
    def pdp_penale_link_local_document(id_fasc: str, case_id: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            require_pdp_penale_case(repo, case_id, fascicolo.id)
            gestore_fascicoli = get_fascicoli()
            local_doc_id = str(request.form.get("local_doc_id") or "").strip()
            document_role = str(request.form.get("document_role") or "other").strip()
            local_doc = next(
                (documento for documento in fascicolo.documenti if documento.id == local_doc_id),
                None,
            )
            if not local_doc:
                raise ValueError("Documento locale non trovato.")
            file_path = str(gestore_fascicoli.percorso_documento(fascicolo.id, local_doc_id))
            existing = next(
                (
                    row
                    for row in repo.list_case_documents(case_id)
                    if str(row.get("file_path") or "").strip() == file_path
                ),
                None,
            )
            if existing:
                flash("Documento gia collegato al modulo PDP Penale.", "info")
                return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))

            module_doc = repo.add_document(
                case_id,
                document_role=document_role,
                title=str(request.form.get("title") or local_doc.nome).strip() or local_doc.nome,
                original_filename=local_doc.nome,
                stored_filename=local_doc.nome,
                file_path=file_path,
                file_size_bytes=int(getattr(local_doc, "dimensione_bytes", 0) or 0),
                sha256=str(getattr(local_doc, "hash_sha256", "") or "").strip() or None,
                source_type="manual",
                signed=int(bool(getattr(local_doc, "firmato_digitalmente", False))),
                minister_document_date=str(getattr(local_doc, "data_documento", "") or "").strip()
                or None,
                notes=str(request.form.get("notes") or getattr(local_doc, "note", "") or "").strip()
                or None,
            )
            repo.add_event(
                case_id,
                event_type="document_linked",
                event_source="user",
                title="Documento della pratica collegato al workflow PDP",
                description=f"{local_doc.nome} -> {document_role}",
                payload_json={"document_id": module_doc["id"], "local_doc_id": local_doc_id},
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            if document_role == "nomination":
                repo.update_case(case_id, nomination_status="deposited")
            audit(
                "fascicoli.pdp_penale.documento",
                "fascicolo",
                id_fasc,
                dettagli=f"Collega documento {local_doc_id} al case {case_id}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            flash("Documento collegato al workflow PDP Penale.", "success")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))
        except Exception as exc:
            app.logger.exception(
                "Errore pdp_penale_link_local_document(%s, %s): %s",
                id_fasc,
                case_id,
                exc,
            )
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case/<case_id>/access-request", methods=["POST"])
    def pdp_penale_create_access_request(id_fasc: str, case_id: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            require_pdp_penale_case(repo, case_id, fascicolo.id)
            form = request.form
            request_status = str(form.get("request_status") or "prepared").strip()
            ministry_status = str(form.get("ministry_status") or "").strip() or None
            download_until = str(form.get("download_available_until") or "").strip() or None
            request_reference = str(form.get("request_reference") or "").strip() or pdp_penale_request_reference(
                repo.get_case(case_id)
            )
            access_request = repo.create_access_request(
                case_id,
                request_type=str(form.get("request_type") or "access_to_case_file").strip(),
                request_reference=request_reference,
                request_status=request_status,
                submitted_at=str(form.get("submitted_at") or "").strip() or None,
                office_response_at=str(form.get("office_response_at") or "").strip() or None,
                authorized_at=str(form.get("authorized_at") or "").strip() or None,
                denied_at=str(form.get("denied_at") or "").strip() or None,
                payment_required=int(pdp_penale_bool(form.get("payment_required"))),
                payment_amount=pdp_penale_float(form.get("payment_amount"), 0.0) or None,
                payment_due_date=str(form.get("payment_due_date") or "").strip() or None,
                payment_done=int(pdp_penale_bool(form.get("payment_done"))),
                legal_aid_declared=int(pdp_penale_bool(form.get("legal_aid_declared"))),
                pec_password_received_at=str(form.get("pec_password_received_at") or "").strip()
                or None,
                download_link_available=int(bool(download_until)),
                download_available_until=download_until,
                downloaded_at=str(form.get("downloaded_at") or "").strip() or None,
                ministry_status=ministry_status,
                notes=str(form.get("notes") or "").strip() or None,
            )
            case_changes: dict[str, Any] = {
                "access_status": pdp_penale_access_status_from_request_status(request_status),
                "current_ministry_status": ministry_status,
            }
            if download_until:
                case_changes["download_available_until"] = download_until
            if request_status == "downloaded":
                case_changes["import_status"] = "downloaded"
            repo.update_case(case_id, **case_changes)
            repo.add_event(
                case_id,
                event_type="access_request_registered",
                event_source="user",
                title="Richiesta accesso atti registrata",
                description=(
                    f"{access_request['request_type']} - {pdp_penale_status_label(request_status)}"
                ),
                payload_json={
                    "access_request_id": access_request["id"],
                    "request_status": request_status,
                    "ministry_status": ministry_status or "",
                },
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            audit(
                "fascicoli.pdp_penale.access_request",
                "fascicolo",
                id_fasc,
                dettagli=f"Richiesta {access_request['id']} sul case {case_id}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            flash("Richiesta di accesso atti registrata.", "success")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))
        except Exception as exc:
            app.logger.exception(
                "Errore pdp_penale_create_access_request(%s, %s): %s",
                id_fasc,
                case_id,
                exc,
            )
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case/<case_id>/generate-request", methods=["POST"])
    def pdp_penale_generate_access_request(id_fasc: str, case_id: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            case_row = require_pdp_penale_case(repo, case_id, fascicolo.id)
            gestore_fascicoli = get_fascicoli()
            cliente = get_clienti().get(fascicolo.id_cliente) if fascicolo.id_cliente else None
            local_documents = pdp_penale_local_documents(fascicolo, gestore_fascicoli)
            module_documents = pdp_penale_module_documents_enriched(
                fascicolo,
                gestore_fascicoli,
                repo.list_case_documents(case_id),
            )
            nomination_docs = [
                doc
                for doc in (local_documents + module_documents)
                if str(doc.get("role_suggestion") or doc.get("document_role") or "") == "nomination"
            ]
            payment_docs = [
                doc
                for doc in (local_documents + module_documents)
                if str(doc.get("role_suggestion") or doc.get("document_role") or "")
                == "payment_receipt"
            ]
            legal_aid_docs = [
                doc
                for doc in (local_documents + module_documents)
                if str(doc.get("role_suggestion") or doc.get("document_role") or "")
                == "legal_aid_order"
            ]
            request_reference = pdp_penale_request_reference(case_row)
            pdf_bytes = pdp_penale_generate_request_pdf(
                fascicolo,
                cliente,
                case_row,
                request_reference=request_reference,
                nomination_docs=nomination_docs,
                payment_docs=payment_docs,
                legal_aid_docs=legal_aid_docs,
            )
            nome_file = (
                f"richiesta_accesso_pdp_{case_row.get('register_number')}_{case_row.get('register_year')}.pdf"
            ).replace(" ", "_")
            documento = salva_documento_fascicolo(
                gf=gestore_fascicoli,
                id_fasc=fascicolo.id,
                nome_file=nome_file,
                raw=pdf_bytes,
                tipo_doc=TipoDocumento.ATTO_GIUDIZIARIO,
                note="Richiesta accesso atti PDP generata dal workflow.",
                data_documento=date.today().isoformat(),
                firmato=False,
                caricato_da=getattr(g.utente_corrente, "username", ""),
            )
            file_path = str(gestore_fascicoli.percorso_documento(fascicolo.id, documento.id))
            module_doc = repo.add_document(
                case_id,
                document_role="access_request",
                document_category="istanza_accesso",
                title="Richiesta accesso atti PDP Penale",
                original_filename=documento.nome,
                stored_filename=documento.nome,
                file_path=file_path,
                file_size_bytes=int(getattr(documento, "dimensione_bytes", 0) or 0),
                sha256=str(getattr(documento, "hash_sha256", "") or "").strip() or None,
                source_type="generated",
                signed=0,
                notes="Generato dal workflow PDP Penale.",
            )
            existing_requests = repo.list_access_requests(case_id)
            request_row = pdp_penale_primary_access_request(existing_requests)
            if request_row and request_row.get("id"):
                request_row = repo.update_access_request(
                    str(request_row["id"]),
                    request_reference=request_reference,
                    request_status="prepared",
                )
            else:
                request_row = repo.create_access_request(
                    case_id,
                    request_type="access_to_case_file",
                    request_reference=request_reference,
                    request_status="prepared",
                    notes="Richiesta generata automaticamente dal workflow PDP Penale.",
                )
            repo.link_document_to_access_request(
                str(request_row["id"]),
                str(module_doc["id"]),
                relation_type="generated_request",
            )
            repo.update_case(case_id, access_status="ready")
            repo.add_event(
                case_id,
                event_type="access_request_generated",
                event_source="system",
                title="Richiesta accesso atti generata",
                description=f"{request_reference} - {documento.nome}",
                payload_json={
                    "access_request_id": request_row["id"],
                    "document_id": module_doc["id"],
                },
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            audit(
                "fascicoli.pdp_penale.generate_request",
                "fascicolo",
                id_fasc,
                dettagli=f"Richiesta {request_row['id']} generata sul case {case_id}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            flash("Richiesta di accesso atti generata e salvata nel fascicolo.", "success")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))
        except Exception as exc:
            app.logger.exception(
                "Errore pdp_penale_generate_access_request(%s, %s): %s",
                id_fasc,
                case_id,
                exc,
            )
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case/<case_id>/deposit", methods=["POST"])
    def pdp_penale_deposit_request(id_fasc: str, case_id: str):
        import tempfile

        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            case_row = require_pdp_penale_case(repo, case_id, fascicolo.id)
            local_doc_id = str(request.form.get("local_doc_id") or "").strip()
            if not local_doc_id:
                raise ValueError("Seleziona il documento da depositare.")
            documento = pdp_penale_find_case_local_document(fascicolo, local_doc_id)
            if not documento:
                raise ValueError("Documento locale non trovato.")
            demo_mode = polis_demo_mode()
            if not demo_mode and not bool(getattr(documento, "firmato_digitalmente", False)):
                raise ValueError(
                    "Il deposito reale PDP richiede un file firmato. Firma prima il PDF e poi riprova."
                )
            gestore_fascicoli = get_fascicoli()
            percorso = gestore_fascicoli.percorso_documento(fascicolo.id, documento.id)
            payload = decrypt_doc(Path(percorso).read_bytes())
            suffix = "".join(Path(documento.nome).suffixes) or Path(documento.nome).suffix or ".pdf"
            with tempfile.NamedTemporaryFile(prefix="pdp_", suffix=suffix, delete=False) as tmp_file:
                tmp_file.write(payload)
                tmp_path = tmp_file.name
            try:
                office = resolve_ufficio_destinatario(str(case_row.get("office_name") or ""))
                codice_ufficio = str(
                    (office or {}).get("codice") or case_row.get("office_name") or ""
                ).strip()
                tipo_atto = str(request.form.get("tipo_atto") or "RICHIESTA").strip().upper()
                oggetto = str(
                    request.form.get("oggetto")
                    or (
                        "Richiesta accesso atti - "
                        f"{case_row.get('register_type') or 'RGNR'} "
                        f"{case_row.get('register_number')}/{case_row.get('register_year')}"
                    )
                ).strip()
                from pct.pdp import crea_client_pdp

                client = crea_client_pdp(demo=demo_mode)
                esito = client.deposita_atto(
                    codice_ufficio=codice_ufficio,
                    tipo_atto=tipo_atto,
                    atto_path=tmp_path,
                    numero_rg=str(case_row.get("register_number") or "").strip(),
                    anno_rg=int(case_row.get("register_year") or 0),
                    oggetto=oggetto,
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            codice_esito = str(esito.get("codiceEsito") or "").strip()
            stato = str(esito.get("stato") or "").strip() or (
                "INVIATO" if codice_esito in {"0", "1"} else ""
            )
            success = codice_esito in {"0", "1"} and stato != "ERRORE"
            existing_requests = repo.list_access_requests(case_id)
            request_row = pdp_penale_primary_access_request(existing_requests)
            submitted_at = str(esito.get("dataDeposito") or datetime.now().isoformat(timespec="minutes"))
            if request_row and request_row.get("id"):
                repo.update_access_request(
                    str(request_row["id"]),
                    request_status="submitted" if success else "technical_error",
                    request_reference=str(
                        esito.get("idDeposito")
                        or request_row.get("request_reference")
                        or pdp_penale_request_reference(case_row)
                    ),
                    submitted_at=submitted_at,
                    ministry_status=stato or None,
                    notes=str(esito.get("descrizioneEsito") or "").strip() or None,
                )
            else:
                request_row = repo.create_access_request(
                    case_id,
                    request_type="access_to_case_file",
                    request_reference=str(
                        esito.get("idDeposito") or pdp_penale_request_reference(case_row)
                    ),
                    request_status="submitted" if success else "technical_error",
                    submitted_at=submitted_at,
                    ministry_status=stato or None,
                    notes=str(esito.get("descrizioneEsito") or "").strip() or None,
                )
            repo.update_case(
                case_id,
                access_status="submitted" if success else "technical_error",
                current_ministry_status=(
                    stato
                    if stato
                    in {
                        "INVIATO",
                        "IN_TRANSITO",
                        "ACCETTATO",
                        "IN_VERIFICA",
                        "RIFIUTATO",
                        "ERRORE_TECNICO",
                    }
                    else None
                ),
                notes=str(esito.get("descrizioneEsito") or case_row.get("notes") or "").strip()
                or None,
            )
            repo.add_event(
                case_id,
                event_type="deposit_submitted" if success else "deposit_failed",
                event_source="ministry" if success else "system",
                title="Deposito PDP inviato" if success else "Deposito PDP non riuscito",
                description=str(esito.get("descrizioneEsito") or "").strip() or oggetto,
                payload_json=esito,
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            if success:
                existing_tasks = repo.list_tasks(case_id, only_open=True)
                if not any(str(task.get("task_type") or "") == "check_pec" for task in existing_tasks):
                    repo.create_task(
                        case_id,
                        task_type="check_pec",
                        title="Controllare la PEC per password ed esiti PDP",
                        description="Il deposito e stato inviato. Attendere PEC con esiti e password.",
                        priority="high",
                        status="open",
                        assigned_user_id=getattr(g.utente_corrente, "id", "") or None,
                    )
                if not any(
                    str(task.get("task_type") or "") == "wait_office_response"
                    for task in existing_tasks
                ):
                    repo.create_task(
                        case_id,
                        task_type="wait_office_response",
                        title="Monitorare autorizzazione ufficio PDP",
                        description="Verificare stato inviato / in verifica / accettato / rifiutato.",
                        priority="medium",
                        status="open",
                        assigned_user_id=getattr(g.utente_corrente, "id", "") or None,
                    )
            audit(
                "fascicoli.pdp_penale.deposit",
                "fascicolo",
                id_fasc,
                dettagli=f"Deposito PDP case {case_id}: {stato or codice_esito}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            flash(
                "Deposito PDP registrato: "
                + str(esito.get("descrizioneEsito") or stato or "esito non disponibile"),
                "success" if success else "warning",
            )
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))
        except Exception as exc:
            app.logger.exception(
                "Errore pdp_penale_deposit_request(%s, %s): %s",
                id_fasc,
                case_id,
                exc,
            )
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case/<case_id>/sync-pec", methods=["POST"])
    def pdp_penale_sync_pec(id_fasc: str, case_id: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            case_row = require_pdp_penale_case(repo, case_id, fascicolo.id)
            result = pdp_penale_sync_case_mailbox(
                fascicolo,
                case_row,
                repo.list_access_requests(case_id),
            )
            audit(
                "fascicoli.pdp_penale.sync_pec",
                "fascicolo",
                id_fasc,
                dettagli=f"matched={result['matched']} password={result['password_found']}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            if result["matched"]:
                msg = f"Sincronizzazione PEC completata: {result['matched']} messaggi associati."
                if result["password_found"]:
                    msg += f" Password trovata in {result['password_found']} PEC."
                if result["download_available_until"]:
                    msg += f" Download disponibile fino a {result['download_available_until']}."
                flash(msg, "success")
            elif str((result.get("sync_result") or {}).get("errore") or "").strip():
                flash(
                    "Sincronizzazione IMAP non completata: "
                    + str(result["sync_result"]["errore"]),
                    "warning",
                )
            else:
                flash("Nessuna nuova PEC PDP associabile al fascicolo.", "info")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))
        except Exception as exc:
            app.logger.exception("Errore pdp_penale_sync_pec(%s, %s): %s", id_fasc, case_id, exc)
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case/<case_id>/import-download", methods=["POST"])
    def pdp_penale_import_download(id_fasc: str, case_id: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            case_row = require_pdp_penale_case(repo, case_id, fascicolo.id)
            note_importazione = str(request.form.get("note_importazione") or "").strip()
            uploaded_items: list[dict[str, Any]] = []
            for storage in request.files.getlist("files"):
                if not storage or not storage.filename:
                    continue
                payload = storage.read()
                if not payload:
                    continue
                uploaded_items.extend(
                    espandi_file_importato_portale(
                        nome_file=storage.filename,
                        contenuto=payload,
                        data_documento=date.today().isoformat(),
                        origine=f"upload:{storage.filename}",
                    )
                )
            staging_items: list[dict[str, Any]] = []
            staging_dir = pst_import_dir_for_fascicolo(fascicolo)
            usa_staging = not uploaded_items
            if usa_staging:
                staging_items, staging_dir = leggi_staging_documenti_portale(fascicolo)
            items = uploaded_items or staging_items
            if not items:
                raise ValueError(
                    "Nessun file trovato. Carica ZIP/cartella scaricati dal PDP oppure usa l'inbox tecnica del fascicolo."
                )
            esito_import = pdp_penale_import_download_items(
                fascicolo,
                case_row,
                items=items,
                note_importazione=note_importazione,
            )
            staging_archived = ""
            if usa_staging and staging_dir is not None:
                staging_archived = archivia_staging_documenti_portale(staging_dir)
            audit(
                "fascicoli.pdp_penale.import_download",
                "fascicolo",
                id_fasc,
                dettagli=(
                    f"nuovi={len(esito_import['created_local'])} "
                    f"linked={esito_import['linked_module']}"
                ),
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            msg = (
                f"Importazione completata: {len(esito_import['created_local'])} nuovi documenti "
                f"e {esito_import['linked_module']} classificazioni nel workflow."
            )
            if staging_archived:
                msg += " Inbox tecnica archiviata."
            flash(msg, "success")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))
        except Exception as exc:
            app.logger.exception(
                "Errore pdp_penale_import_download(%s, %s): %s",
                id_fasc,
                case_id,
                exc,
            )
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case/<case_id>/pec", methods=["POST"])
    def pdp_penale_register_pec(id_fasc: str, case_id: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            require_pdp_penale_case(repo, case_id, fascicolo.id)
            cfg = get_config_studio().config
            form = request.form
            body_text = str(form.get("body_text") or "").strip()
            subject = str(form.get("subject") or "Comunicazione PDP Penale").strip()
            extracted_password = str(form.get("extracted_password") or "").strip() or pdp_penale_estrai_password(
                body_text,
                subject,
            )
            download_until = (
                str(form.get("download_available_until") or "").strip()
                or pdp_penale_estrai_scadenza_download(
                    body_text,
                    str(form.get("message_date") or "").strip(),
                )
                or None
            )
            pec = repo.register_pec_message(
                criminal_case_id=case_id,
                mailbox=str(form.get("mailbox") or getattr(cfg.pec, "indirizzo", "") or "").strip(),
                subject=subject,
                sender=str(form.get("sender") or "").strip() or None,
                recipient=str(form.get("recipient") or "").strip() or None,
                message_date=str(form.get("message_date") or "").strip() or None,
                body_text=body_text or None,
                raw_eml_path=str(form.get("raw_eml_path") or "").strip() or None,
                matched=1,
                matched_reason="workflow_pdp_penale",
                extracted_password=extracted_password or None,
                contains_download_notice=int(
                    pdp_penale_bool(form.get("contains_download_notice")) or bool(download_until)
                ),
                processed=1,
                processed_at=datetime.now().isoformat(),
            )
            case_changes: dict[str, Any] = {"last_sync_at": datetime.now().isoformat()}
            if download_until:
                case_changes.update(
                    {
                        "download_available_until": download_until,
                        "access_status": "authorized",
                        "import_status": "waiting_download",
                    }
                )
            repo.update_case(case_id, **case_changes)
            repo.add_event(
                case_id,
                event_type="pec_registered",
                event_source="pec",
                title="PEC PDP registrata",
                description=pec.get("subject") or "Comunicazione PEC acquisita",
                payload_json={
                    "pec_message_id": pec["id"],
                    "contains_password": int(pec.get("contains_password") or 0),
                    "download_available_until": download_until or "",
                },
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            audit(
                "fascicoli.pdp_penale.pec",
                "fascicolo",
                id_fasc,
                dettagli=f"PEC {pec['id']} sul case {case_id}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            flash("PEC registrata nel workflow PDP Penale.", "success")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))
        except Exception as exc:
            app.logger.exception("Errore pdp_penale_register_pec(%s, %s): %s", id_fasc, case_id, exc)
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case/<case_id>/task", methods=["POST"])
    def pdp_penale_create_task(id_fasc: str, case_id: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            require_pdp_penale_case(repo, case_id, fascicolo.id)
            form = request.form
            task = repo.create_task(
                case_id,
                task_type=str(form.get("task_type") or "other").strip(),
                title=str(form.get("title") or "").strip() or "Task operativo PDP",
                description=str(form.get("description") or "").strip() or None,
                priority=str(form.get("priority") or "medium").strip(),
                due_at=str(form.get("due_at") or "").strip() or None,
                status="open",
                assigned_user_id=getattr(g.utente_corrente, "id", "") or None,
            )
            repo.add_event(
                case_id,
                event_type="task_created",
                event_source="user",
                title="Task operativo creato",
                description=task.get("title") or "",
                payload_json={"task_id": task["id"], "priority": task.get("priority") or ""},
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            audit(
                "fascicoli.pdp_penale.task",
                "fascicolo",
                id_fasc,
                dettagli=f"Task {task['id']} sul case {case_id}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            flash("Task operativo PDP creato.", "success")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))
        except Exception as exc:
            app.logger.exception("Errore pdp_penale_create_task(%s, %s): %s", id_fasc, case_id, exc)
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case_id))

    @app.route("/fascicoli/<id_fasc>/penale/pdp/task/<task_id>/complete", methods=["POST"])
    def pdp_penale_complete_task(id_fasc: str, task_id: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            task = repo.get_task(task_id)
            case = require_pdp_penale_case(
                repo,
                str(task.get("criminal_case_id") or ""),
                fascicolo.id,
            )
            completion_note = str(request.form.get("completion_note") or "").strip()
            closed = repo.close_task(task_id, completion_note=completion_note or None)
            repo.add_event(
                str(case["id"]),
                event_type="task_completed",
                event_source="user",
                title="Task operativo completato",
                description=closed.get("title") or "",
                payload_json={"task_id": closed["id"]},
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            audit(
                "fascicoli.pdp_penale.task_complete",
                "fascicolo",
                id_fasc,
                dettagli=f"Task {task_id} completato",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            flash("Task operativo segnato come completato.", "success")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case["id"]))
        except Exception as exc:
            app.logger.exception("Errore pdp_penale_complete_task(%s, %s): %s", id_fasc, task_id, exc)
            flash(str(exc), "danger")
            return redirect(url_for("pdp_penale_workspace", id_fasc=id_fasc))
