"""Runtime PDP Penale estratto da web.app."""

from __future__ import annotations

import io
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

from flask import Flask, g, request, url_for

from pct.clienti import Cliente
from pct.fascicoli import Documento, Fascicolo, GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.pdp_penale_workflow import (
    PDPPenaleWorkflowRepository,
    pdp_penale_classifica_documento,
    pdp_penale_estrai_password,
    pdp_penale_estrai_scadenza_download,
)


def build_pdp_penale_runtime(
    app: Flask,
    *,
    get_pdp_penale,
    get_fascicoli,
    get_config_studio,
    get_clienti,
    audit,
    sync_pubblica,
    resolve_ufficio_destinatario,
    polis_demo_mode,
    salva_documento_fascicolo,
    espandi_file_importato_portale,
    pst_import_dir_for_fascicolo,
    leggi_staging_documenti_portale,
    archivia_staging_documenti_portale,
    normalizza_nome_match_portale,
    fascicolo_text,
) -> dict[str, Any]:
    _resolve_ufficio_destinatario = resolve_ufficio_destinatario
    _polis_demo_mode = polis_demo_mode
    _salva_documento_fascicolo = salva_documento_fascicolo
    _espandi_file_importato_portale = espandi_file_importato_portale
    _pst_import_dir_for_fascicolo = pst_import_dir_for_fascicolo
    _leggi_staging_documenti_portale = leggi_staging_documenti_portale
    _archivia_staging_documenti_portale = archivia_staging_documenti_portale
    _normalizza_nome_match_portale = normalizza_nome_match_portale
    _fascicolo_text = fascicolo_text

    def _normalize_portale_match_text(value: Any) -> str:
        text = str(value or "").strip().upper()
        text = re.sub(r"\s+", " ", text)
        return text

    def _pdp_penale_bool(value: Any) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "on", "si", "yes"}

    def _pdp_penale_int(value: Any, default: int = 0) -> int:
        try:
            return int(str(value or "").strip())
        except Exception:
            return default

    def _pdp_penale_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(str(value or "").strip().replace(",", "."))
        except Exception:
            return default

    def _pdp_penale_status_label(value: Any) -> str:
        testo = str(value or "").strip()
        return testo.replace("_", " ").title() if testo else "â€”"

    def _pdp_penale_guess_office_type(office_name: str) -> str:
        testo = str(office_name or "").strip().lower()
        if "procura" in testo:
            return "Procura"
        if "gip" in testo or "gup" in testo:
            return "GIP/GUP"
        if "tribunale" in testo:
            return "Tribunale"
        if "corte" in testo:
            return "Corte"
        return ""

    def _pdp_penale_guess_district(office_name: str) -> str:
        testo = str(office_name or "").strip()
        if " di " in testo:
            return testo.split(" di ", 1)[1].strip()
        return ""

    def _require_pdp_penale_fascicolo(id_fasc: str) -> Fascicolo:
        fasc = get_fascicoli().get(id_fasc)
        if not fasc:
            raise KeyError("Fascicolo non trovato.")
        if fasc.tipo != TipoFascicolo.PENALE:
            raise ValueError("Il modulo PDP Penale Ã¨ disponibile solo per i fascicoli penali.")
        return fasc

    def _require_pdp_penale_case(repo: PDPPenaleWorkflowRepository, case_id: str, practice_id: str) -> dict[str, Any]:
        case = repo.get_case(case_id)
        if str(case.get("practice_id") or "") != str(practice_id):
            raise ValueError("Il fascicolo ministeriale PDP non appartiene a questa pratica.")
        return case

    def _pdp_penale_case_defaults(fasc: Fascicolo, cliente: Optional[Cliente] = None) -> dict[str, Any]:
        cfg = get_config_studio().config
        counsel_name = (
            fasc.avvocato_referente
            or fasc.avvocato_dominus
            or getattr(cfg.studio, "avvocato", "")
            or getattr(g.utente_corrente, "nome_completo", "")
            or getattr(g.utente_corrente, "username", "")
        )
        counsel_cf = (
            getattr(cfg.firma, "cf_avvocato", "")
            or getattr(cfg.studio, "codice_fiscale_avvocato", "")
            or ""
        ).strip().upper()
        office_name = str(fasc.tribunale or "").strip()
        register_number = str(fasc.numero_rg or fasc.numero or "").strip()
        register_year = int(fasc.anno_rg or date.today().year)
        assisted_party_name = (
            getattr(cliente, "nome_completo", "")
            or str(fasc.nome_cliente or "").strip()
            or str(fasc.controparte or "").strip()
        )
        assisted_party_cf = getattr(cliente, "codice_fiscale", "") if cliente else ""
        return {
            "practice_id": fasc.id,
            "minister_case_ref": str(fasc.source_external_id or "").strip(),
            "office_name": office_name,
            "office_type": _pdp_penale_guess_office_type(office_name),
            "district": _pdp_penale_guess_district(office_name),
            "register_type": str(fasc.tipo_procedimento or "RGNR").strip() or "RGNR",
            "register_number": register_number,
            "register_year": register_year,
            "proceeding_type": str(fasc.tipo_procedimento or "procedimento_penale").strip(),
            "prosecutor_name": "",
            "judge_name": str(fasc.giudice or "").strip(),
            "chamber_section": str(fasc.sezione or "").strip(),
            "assisted_party_name": assisted_party_name,
            "assisted_party_cf": assisted_party_cf,
            "defense_counsel_name": str(counsel_name or "").strip(),
            "defense_counsel_cf": counsel_cf,
            "nomination_status": "missing",
            "access_status": "draft",
            "import_status": "not_started",
            "current_ministry_status": "",
            "notes": "",
        }

    def _ensure_pdp_penale_case_after_import(
        *,
        id_fasc: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        user_name: str,
        imported_documents: int = 0,
        downloaded_files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        fasc = get_fascicoli().get(id_fasc)
        if not fasc or getattr(getattr(fasc, "tipo", None), "value", "") != "PENALE":
            return {}
        cliente = get_clienti().get(fasc.id_cliente) if fasc.id_cliente else None
        defaults = _pdp_penale_case_defaults(fasc, cliente)
        payload = dict(selection.get("payload") or {})
        identity = dict(preview.get("identity") or {})
        repository = get_pdp_penale()
        minister_status = str(
            payload.get("ministry_status")
            or selection.get("current_ministry_status")
            or ""
        ).strip().upper()
        if minister_status not in {
            "INVIATO",
            "IN_TRANSITO",
            "ACCETTATO",
            "IN_VERIFICA",
            "RIFIUTATO",
            "ERRORE_TECNICO",
        }:
            minister_status = ""
        case_payload = dict(defaults)
        case_payload.update(
            {
                "practice_id": fasc.id,
                "minister_case_ref": str(
                    selection.get("external_id")
                    or payload.get("id_fascicolo")
                    or defaults.get("minister_case_ref")
                    or ""
                ).strip()
                or None,
                "office_name": str(selection.get("ufficio_nome") or defaults["office_name"]).strip(),
                "register_type": str(
                    selection.get("procedimento")
                    or payload.get("tipo_registro")
                    or defaults["register_type"]
                ).strip()
                or defaults["register_type"],
                "register_number": str(selection.get("numero") or defaults["register_number"]).strip(),
                "register_year": int(selection.get("anno") or defaults["register_year"] or date.today().year),
                "proceeding_type": str(
                    payload.get("fase")
                    or payload.get("tipo_registro")
                    or defaults["proceeding_type"]
                ).strip()
                or defaults["proceeding_type"],
                "judge_name": str(payload.get("giudice") or defaults["judge_name"]).strip(),
                "chamber_section": str(selection.get("sezione") or payload.get("sezione") or defaults["chamber_section"]).strip(),
                "assisted_party_name": str(
                    (selection.get("parti") or [defaults["assisted_party_name"]])[0]
                    if (selection.get("parti") or [defaults["assisted_party_name"]])
                    else defaults["assisted_party_name"]
                ).strip(),
                "current_ministry_status": minister_status or None,
            }
        )
        available_docs = int(preview.get("counts", {}).get("documenti", 0) or 0)
        downloaded_count = len(downloaded_files or [])
        if imported_documents > 0 or downloaded_count > 0:
            case_payload["import_status"] = "completed"
        elif available_docs > 0:
            case_payload["import_status"] = "waiting_download"
        office_name_norm = _normalize_portale_match_text(case_payload["office_name"])
        register_type_norm = _normalize_portale_match_text(case_payload["register_type"])
        register_number = str(case_payload["register_number"] or "").strip()
        register_year = int(case_payload["register_year"] or 0)
        minister_ref = str(case_payload.get("minister_case_ref") or "").strip()
        current_case = None
        for row in repository.list_cases_for_practice(fasc.id):
            if minister_ref and str(row.get("minister_case_ref") or "").strip() == minister_ref:
                current_case = row
                break
            if (
                _normalize_portale_match_text(row.get("office_name")) == office_name_norm
                and _normalize_portale_match_text(row.get("register_type")) == register_type_norm
                and str(row.get("register_number") or "").strip() == register_number
                and int(row.get("register_year") or 0) == register_year
            ):
                current_case = row
                break
        if current_case:
            case = repository.update_case(str(current_case["id"]), **case_payload)
            event_type = "guided_import_synced"
            title = "Workflow PDP aggiornato dall'acquisizione guidata"
        else:
            case = repository.create_case(**case_payload)
            event_type = "guided_import_created"
            title = "Workflow PDP creato dall'acquisizione guidata"
        repository.add_event(
            str(case["id"]),
            event_type=event_type,
            event_source="import",
            title=title,
            description=f"{case_payload['register_type']} {case_payload['register_number']}/{case_payload['register_year']}",
            payload_json={
                "import_status": case_payload.get("import_status") or "",
                "available_documents": available_docs,
                "imported_documents": imported_documents,
            },
            created_by_user_id=getattr(g.utente_corrente, "id", "") or user_name,
        )
        return case

    def _pdp_penale_workspace_url_for_fascicolo(id_fasc: str) -> str:
        id_fasc = str(id_fasc or "").strip()
        if not id_fasc:
            return ""
        try:
            cases = get_pdp_penale().list_cases_for_practice(id_fasc)
        except Exception:
            cases = []
        active_case = next(
            (
                row
                for row in cases
                if str(row.get("id") or "").strip()
            ),
            None,
        )
        if active_case:
            return url_for(
                "pdp_penale_workspace",
                id_fasc=id_fasc,
                case_id=str(active_case["id"]),
            )
        return url_for("pdp_penale_workspace", id_fasc=id_fasc)

    def _pdp_penale_access_status_from_request_status(request_status: str) -> str:
        mapping = {
            "draft": "draft",
            "prepared": "ready",
            "submitted": "submitted",
            "in_review": "waiting_authorization",
            "authorized": "authorized",
            "denied": "denied",
            "expired": "expired",
            "technical_error": "technical_error",
            "downloaded": "authorized",
            "closed": "authorized",
        }
        return mapping.get(str(request_status or "").strip(), "draft")

    def _pdp_penale_local_documents(fasc: Fascicolo, gf: GestioneFascicoli) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc in sorted(fasc.documenti or [], key=lambda item: item.data_caricamento or "", reverse=True):
            try:
                percorso = gf.percorso_documento(fasc.id, doc.id)
            except Exception:
                continue
            testo = _fascicolo_text(
                getattr(doc, "nome", ""),
                getattr(doc, "note", ""),
                getattr(getattr(doc, "tipo", None), "value", getattr(doc, "tipo", "")),
            )
            ruolo = "other"
            if "nomina" in testo or "procura" in testo:
                ruolo = "nomination"
            elif "accesso" in testo or "istanza" in testo or "richiesta" in testo:
                ruolo = "access_request"
            elif "pagopa" in testo or "contribut" in testo or "ricevuta" in testo:
                ruolo = "payment_receipt"
            elif "gratuito patrocinio" in testo or "patrocinio" in testo:
                ruolo = "legal_aid_order"
            elif "verbale" in testo:
                ruolo = "hearing_minutes"
            elif "ordinanza" in testo:
                ruolo = "ordinance"
            elif "sentenza" in testo:
                ruolo = "judgment"
            elif "decreto" in testo:
                ruolo = "decree"
            elif "memoria" in testo or "difesa" in testo:
                ruolo = "defense_brief"
            rows.append(
                {
                    "id": doc.id,
                    "nome": doc.nome,
                    "tipo": getattr(getattr(doc, "tipo", None), "value", ""),
                    "note": doc.note,
                    "percorso": str(percorso),
                    "dimensione_bytes": int(getattr(doc, "dimensione_bytes", 0) or 0),
                    "firmato": bool(getattr(doc, "firmato_digitalmente", False)),
                    "hash_sha256": str(getattr(doc, "hash_sha256", "") or "").strip(),
                    "role_suggestion": ruolo,
                    "data_documento": str(getattr(doc, "data_documento", "") or "").strip(),
                }
            )
        return rows

    def _pdp_penale_tipo_documento_locale(document_role: str) -> TipoDocumento:
        mapping = {
            "nomination": TipoDocumento.PROCURA,
            "access_request": TipoDocumento.ATTO_GIUDIZIARIO,
            "payment_receipt": TipoDocumento.COMUNICAZIONE,
            "legal_aid_order": TipoDocumento.ALLEGATO,
            "pec_message": TipoDocumento.COMUNICAZIONE,
            "download_package": TipoDocumento.ALLEGATO,
            "ministry_document": TipoDocumento.ALLEGATO,
            "hearing_minutes": TipoDocumento.VERBALE,
            "decree": TipoDocumento.DECRETO,
            "ordinance": TipoDocumento.ORDINANZA,
            "judgment": TipoDocumento.SENTENZA,
            "defense_brief": TipoDocumento.MEMORIA,
            "attachment": TipoDocumento.ALLEGATO,
            "other": TipoDocumento.ALLEGATO,
        }
        return mapping.get(str(document_role or "").strip(), TipoDocumento.ALLEGATO)

    def _pdp_penale_primary_access_request(access_requests: list[dict[str, Any]]) -> dict[str, Any]:
        aperte = [
            row for row in (access_requests or [])
            if str(row.get("request_status") or "").strip() not in {"closed", "expired", "denied"}
        ]
        return dict((aperte or access_requests or [{}])[0])

    def _pdp_penale_download_state(download_until: str) -> str:
        testo = str(download_until or "").strip()
        if not testo:
            return "missing"
        try:
            deadline = datetime.fromisoformat(testo.replace("Z", "+00:00"))
        except Exception:
            return "scheduled"
        now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.now()
        return "expired" if deadline < now else "open"

    def _pdp_penale_module_documents_enriched(
        fasc: Fascicolo,
        gf: GestioneFascicoli,
        module_documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        local_by_path: dict[str, Documento] = {}
        for doc in fasc.documenti or []:
            try:
                local_by_path[str(gf.percorso_documento(fasc.id, doc.id))] = doc
            except Exception:
                continue
        enriched: list[dict[str, Any]] = []
        for row in module_documents:
            item = dict(row)
            local_doc = local_by_path.get(str(item.get("file_path") or "").strip())
            if local_doc:
                item["local_doc_id"] = local_doc.id
                item["view_url"] = url_for("visualizza_documento", id_fasc=fasc.id, id_doc=local_doc.id)
                item["download_url"] = url_for("scarica_documento", id_fasc=fasc.id, id_doc=local_doc.id)
            classification = pdp_penale_classifica_documento(
                str(item.get("original_filename") or item.get("title") or ""),
                str(item.get("title") or ""),
                str(item.get("notes") or ""),
            )
            item["document_category"] = item.get("document_category") or classification["document_category"]
            enriched.append(item)
        return enriched

    def _pdp_penale_build_deposit_documents(local_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidati = [
            dict(doc)
            for doc in (local_documents or [])
            if doc.get("firmato") or doc.get("role_suggestion") in {"access_request", "defense_brief", "nomination"}
        ]
        return candidati or list(local_documents or [])

    def _pdp_penale_request_reference(case_row: dict[str, Any]) -> str:
        numero = re.sub(r"[^A-Za-z0-9]+", "", str(case_row.get("register_number") or "").upper()) or "CASE"
        stamp = datetime.now().strftime("%Y%m%d%H%M")
        return f"PDP-ACCESS-{numero}-{stamp}"

    def _pdp_penale_generate_request_pdf(
        fasc: Fascicolo,
        cliente: Optional[Cliente],
        case_row: dict[str, Any],
        *,
        request_reference: str,
        nomination_docs: list[dict[str, Any]],
        payment_docs: list[dict[str, Any]],
        legal_aid_docs: list[dict[str, Any]],
    ) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            topMargin=36,
            bottomMargin=36,
            leftMargin=42,
            rightMargin=42,
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="PDPBody", parent=styles["BodyText"], leading=15, spaceAfter=6))
        styles.add(ParagraphStyle(name="PDPTitle", parent=styles["Heading1"], textColor=colors.HexColor("#9f1239"), spaceAfter=14))
        story: list[Any] = []
        story.append(Paragraph("Richiesta di accesso al fascicolo PDP Penale", styles["PDPTitle"]))
        story.append(Paragraph(
            "Documento operativo generato dal gestionale per il deposito tramite il Portale Deposito Atti Penale.",
            styles["PDPBody"],
        ))
        righe = [
            ["Riferimento richiesta", request_reference],
            ["Ufficio giudiziario", str(case_row.get("office_name") or "")],
            ["Procedimento", f"{case_row.get('register_type') or 'RGNR'} {case_row.get('register_number')}/{case_row.get('register_year')}"],
            ["Assistito", str(case_row.get("assisted_party_name") or "")],
            ["Codice fiscale assistito", str(case_row.get("assisted_party_cf") or "") or "-"],
            ["Difensore", str(case_row.get("defense_counsel_name") or "")],
            ["Codice fiscale difensore", str(case_row.get("defense_counsel_cf") or "")],
            ["Pratica interna", f"{fasc.numero} - {fasc.titolo}"],
        ]
        table = Table(righe, colWidths=(160, 320))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(table)
        story.append(Spacer(1, 14))
        assisted_cf = str(case_row.get("assisted_party_cf") or "").strip()
        cliente_label = getattr(cliente, "nome_completo", "") if cliente else ""
        story.append(Paragraph(
            (
                f"Il sottoscritto difensore {case_row.get('defense_counsel_name') or '-'} "
                f"chiede l'accesso al fascicolo digitale relativo al procedimento indicato, "
                f"nell'interesse di {case_row.get('assisted_party_name') or cliente_label or '-'}"
                + (f" (CF {assisted_cf})" if assisted_cf else "")
                + "."
            ),
            styles["PDPBody"],
        ))
        allegati = [
            f"Nomina / titolo di accesso: {len(nomination_docs)}",
            f"Ricevute pagamento: {len(payment_docs)}",
            f"Gratuito patrocinio: {len(legal_aid_docs)}",
        ]
        story.append(Paragraph("Checklist allegati predisposti:", styles["Heading3"]))
        for voce in allegati:
            story.append(Paragraph(f"- {voce}", styles["PDPBody"]))
        if case_row.get("notes"):
            story.append(Spacer(1, 10))
            story.append(Paragraph("Note operative", styles["Heading3"]))
            story.append(Paragraph(str(case_row.get("notes") or ""), styles["PDPBody"]))
        story.append(Spacer(1, 14))
        story.append(Paragraph(
            f"Documento generato il {date.today().strftime('%d/%m/%Y')} dal workflow PDP Penale HACS.",
            styles["PDPBody"],
        ))
        doc.build(story)
        return buf.getvalue()

    def _pdp_penale_email_text(email_row: Any) -> str:
        corpo_html = re.sub(r"<[^>]+>", " ", str(getattr(email_row, "corpo_html", "") or ""))
        return " ".join(
            str(part or "").strip()
            for part in [
                getattr(email_row, "oggetto", ""),
                getattr(email_row, "mittente", ""),
                getattr(email_row, "mittente_nome", ""),
                getattr(email_row, "destinatari", ""),
                getattr(email_row, "corpo_testo", ""),
                corpo_html,
            ]
            if str(part or "").strip()
        )

    def _pdp_penale_email_text_search(email_row: Any) -> str:
        return _fascicolo_text(
            getattr(email_row, "oggetto", ""),
            getattr(email_row, "mittente", ""),
            getattr(email_row, "mittente_nome", ""),
            getattr(email_row, "destinatari", ""),
            getattr(email_row, "corpo_testo", ""),
            re.sub(r"<[^>]+>", " ", str(getattr(email_row, "corpo_html", "") or "")),
        )

    def _pdp_penale_match_email_score(
        case_row: dict[str, Any],
        access_requests: list[dict[str, Any]],
        email_row: Any,
    ) -> int:
        testo = _pdp_penale_email_text_search(email_row)
        score = 0
        numero_rg = str(case_row.get("register_number") or "").strip().lower()
        anno_rg = str(case_row.get("register_year") or "").strip()
        if numero_rg and anno_rg and numero_rg in testo and anno_rg in testo:
            score += 6
        minister_ref = str(case_row.get("minister_case_ref") or "").strip().lower()
        if minister_ref and minister_ref in testo:
            score += 5
        office = str(case_row.get("office_name") or "").strip().lower()
        if office and office in testo:
            score += 3
        district = str(case_row.get("district") or "").strip().lower()
        if district and district in testo:
            score += 1
        assisted_tokens = [part for part in re.split(r"\s+", str(case_row.get("assisted_party_name") or "").strip().lower()) if len(part) > 2]
        if assisted_tokens and sum(1 for token in assisted_tokens if token in testo) >= min(2, len(assisted_tokens)):
            score += 3
        for req in access_requests[:3]:
            ref = str(req.get("request_reference") or "").strip().lower()
            if ref and ref in testo:
                score += 4
        if any(token in testo for token in ("password", "download", "fascicolo", "documenti disponibili")):
            score += 1
        return score

    def _pdp_penale_find_case_local_document(fasc: Fascicolo, doc_id: str) -> Documento | None:
        return next((doc for doc in fasc.documenti or [] if str(doc.id) == str(doc_id)), None)

    def _pdp_penale_sync_case_mailbox(
        fasc: Fascicolo,
        case_row: dict[str, Any],
        access_requests: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from pct.email_client import GestioneEmailRicevute

        repo = get_pdp_penale()
        cfg = get_config_studio().config
        email_db = app.config.get("EMAIL_CASELLA_DB", os.environ.get("PCT_EMAIL_DB", "./email/casella.json"))
        ge = GestioneEmailRicevute(db_path=email_db)
        sync_result = {"nuove": 0, "errore": ""}
        if getattr(cfg, "pec", None) and getattr(cfg.pec, "imap_host", "") and getattr(cfg.pec, "indirizzo", "") and getattr(cfg.pec, "password", ""):
            sync_result = ge.sincronizza_imap(
                imap_host=cfg.pec.imap_host,
                imap_port=int(getattr(cfg.pec, "imap_port", 993) or 993),
                username=cfg.pec.indirizzo,
                password=cfg.pec.password,
                use_ssl=bool(getattr(cfg.pec, "use_ssl", True)),
                cartelle_imap=["INBOX"],
                limite=80,
            )
        emails = ge.tutte(cartella="INBOX", data_da=(date.today() - timedelta(days=30)).isoformat())
        existing_pec = repo.list_pec_messages(str(case_row.get("id") or ""))
        existing_headers = {
            str(row.get("message_id_header") or "").strip()
            for row in existing_pec
            if str(row.get("message_id_header") or "").strip()
        }
        matched = 0
        password_found = 0
        latest_deadline = ""
        detected_ministry_status = ""
        now_iso = datetime.now().isoformat(timespec="minutes")
        for email_row in emails:
            header_id = str(getattr(email_row, "message_id", "") or "").strip()
            if header_id and header_id in existing_headers:
                continue
            if _pdp_penale_match_email_score(case_row, access_requests, email_row) < 5:
                continue
            testo = _pdp_penale_email_text(email_row)
            testo_search = testo.lower()
            password = pdp_penale_estrai_password(testo, getattr(email_row, "oggetto", ""))
            scadenza = pdp_penale_estrai_scadenza_download(testo, getattr(email_row, "data", ""))
            if any(token in testo_search for token in ("rifiutat", "rigettat", "dinieg")):
                detected_ministry_status = "RIFIUTATO"
            elif "in verifica" in testo_search:
                detected_ministry_status = "IN_VERIFICA"
            elif any(token in testo_search for token in ("accettat", "autorizzat")) or password:
                detected_ministry_status = "ACCETTATO"
            elif "in transito" in testo_search:
                detected_ministry_status = "IN_TRANSITO"
            repo.register_pec_message(
                criminal_case_id=str(case_row.get("id") or ""),
                mailbox=str(getattr(cfg.pec, "indirizzo", "") or "").strip() or "PEC",
                sender=str(getattr(email_row, "mittente", "") or "").strip() or None,
                recipient=str(getattr(email_row, "destinatari", "") or "").strip() or None,
                subject=str(getattr(email_row, "oggetto", "") or "Comunicazione PDP Penale").strip(),
                message_date=str(getattr(email_row, "data", "") or "").strip() or None,
                message_id_header=header_id or None,
                body_text=str(getattr(email_row, "corpo_testo", "") or "").strip() or None,
                matched=1,
                matched_reason="pdp_penale_mailbox_sync",
                extracted_password=password or None,
                contains_download_notice=int(bool(scadenza) or ("download" in testo_search)),
                processed=1,
                processed_at=now_iso,
            )
            matched += 1
            if password:
                password_found += 1
            if scadenza and (not latest_deadline or scadenza > latest_deadline):
                latest_deadline = scadenza
            if header_id:
                existing_headers.add(header_id)

        case_changes: dict[str, Any] = {"last_sync_at": now_iso}
        if latest_deadline:
            case_changes["download_available_until"] = latest_deadline
            if str(case_row.get("import_status") or "") not in {"completed", "partial_import"}:
                case_changes["import_status"] = "waiting_download"
            case_changes["access_status"] = "authorized"
        if password_found:
            case_changes["pec_password_received"] = 1
        if matched:
            if detected_ministry_status:
                case_changes["current_ministry_status"] = detected_ministry_status
                if detected_ministry_status == "RIFIUTATO":
                    case_changes["access_status"] = "denied"
                elif detected_ministry_status == "IN_VERIFICA":
                    case_changes["access_status"] = "waiting_authorization"
            repo.update_case(str(case_row.get("id") or ""), **case_changes)
            request = _pdp_penale_primary_access_request(access_requests)
            if request and request.get("id"):
                request_changes = {
                    "pec_password_received_at": now_iso,
                    "download_link_available": 1 if latest_deadline else int(bool(request.get("download_link_available"))),
                }
                if detected_ministry_status:
                    request_changes["ministry_status"] = detected_ministry_status
                if latest_deadline:
                    request_changes["download_available_until"] = latest_deadline
                    if str(request.get("request_status") or "") in {"submitted", "in_review", "prepared"}:
                        request_changes["request_status"] = "authorized"
                elif detected_ministry_status == "RIFIUTATO":
                    request_changes["request_status"] = "denied"
                repo.update_access_request(str(request["id"]), **request_changes)
            repo.add_event(
                str(case_row.get("id") or ""),
                event_type="pec_sync_completed",
                event_source="pec",
                title="Sincronizzazione PEC PDP completata",
                description=f"{matched} messaggi associati al fascicolo ministeriale.",
                payload_json={
                    "matched_messages": matched,
                    "password_found": password_found,
                    "download_available_until": latest_deadline,
                    "nuove_email": int(sync_result.get("nuove", 0) or 0),
                },
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            existing_tasks = repo.list_tasks(str(case_row.get("id") or ""), only_open=True)
            if latest_deadline and not any(str(task.get("task_type") or "") == "download_case_file" for task in existing_tasks):
                repo.create_task(
                    str(case_row.get("id") or ""),
                    task_type="download_case_file",
                    title="Scaricare fascicolo PDP entro la finestra disponibile",
                    description=f"Password PEC rilevata automaticamente. Download entro {latest_deadline}.",
                    priority="urgent",
                    due_at=latest_deadline[:10],
                    status="open",
                    assigned_user_id=getattr(g.utente_corrente, "id", "") or None,
                )
        return {
            "matched": matched,
            "password_found": password_found,
            "download_available_until": latest_deadline,
            "sync_result": sync_result,
        }

    def _pdp_penale_import_download_items(
        fasc: Fascicolo,
        case_row: dict[str, Any],
        *,
        items: list[dict[str, Any]],
        note_importazione: str = "",
    ) -> dict[str, Any]:
        gf = get_fascicoli()
        repo = get_pdp_penale()
        existing_module_paths = {
            str(doc.get("file_path") or "").strip()
            for doc in repo.list_case_documents(str(case_row.get("id") or ""))
        }
        existing_docs = {
            _normalizza_nome_match_portale(getattr(doc, "nome", "")): doc
            for doc in (fasc.documenti or [])
            if getattr(doc, "nome", "")
        }
        created_local: list[Documento] = []
        linked_module = 0
        for item in items:
            nome = str(item.get("nome") or "").strip()
            payload = item.get("contenuto", b"")
            if not nome or not payload:
                continue
            classification = pdp_penale_classifica_documento(
                nome,
                str(item.get("tipo_atto") or ""),
                str(item.get("origine") or ""),
            )
            nome_norm = _normalizza_nome_match_portale(nome)
            doc_locale = existing_docs.get(nome_norm)
            if doc_locale is None:
                doc_locale = _salva_documento_fascicolo(
                    gf=gf,
                    id_fasc=fasc.id,
                    nome_file=nome,
                    raw=payload,
                    tipo_doc=_pdp_penale_tipo_documento_locale(classification["document_role"]),
                    note=" | ".join(
                        part for part in [
                            "Importato da pacchetto PDP Penale",
                            note_importazione.strip(),
                            str(item.get("origine") or "").strip(),
                        ] if part
                    ),
                    data_documento=str(item.get("data_documento") or date.today().isoformat()),
                    firmato=nome.lower().endswith(".p7m"),
                    caricato_da=getattr(g.utente_corrente, "username", ""),
                )
                existing_docs[nome_norm] = doc_locale
                created_local.append(doc_locale)
            file_path = ""
            try:
                file_path = str(gf.percorso_documento(fasc.id, doc_locale.id))
            except Exception:
                file_path = ""
            if file_path and file_path not in existing_module_paths:
                repo.add_document(
                    str(case_row.get("id") or ""),
                    document_role=classification["document_role"],
                    document_category=classification["document_category"] or None,
                    title=doc_locale.nome,
                    original_filename=doc_locale.nome,
                    stored_filename=doc_locale.nome,
                    file_path=file_path,
                    file_size_bytes=int(getattr(doc_locale, "dimensione_bytes", 0) or 0),
                    sha256=str(getattr(doc_locale, "hash_sha256", "") or "").strip() or None,
                    source_type="download",
                    signed=int(bool(getattr(doc_locale, "firmato_digitalmente", False))),
                    minister_document_date=str(item.get("data_documento") or "").strip() or None,
                    imported_from_download=1,
                    notes=str(item.get("origine") or "").strip() or None,
                )
                existing_module_paths.add(file_path)
                linked_module += 1
        import_status = "completed"
        if created_local or linked_module:
            unknown_docs = [
                doc for doc in repo.list_case_documents(str(case_row.get("id") or ""))
                if int(doc.get("imported_from_download") or 0) == 1
                and str(doc.get("document_role") or "") in {"other", "attachment"}
            ]
            if unknown_docs:
                import_status = "partial_import"
            repo.update_case(
                str(case_row.get("id") or ""),
                import_status=import_status,
                last_download_at=datetime.now().isoformat(timespec="minutes"),
                access_status="authorized",
            )
            access_requests = repo.list_access_requests(str(case_row.get("id") or ""))
            request = _pdp_penale_primary_access_request(access_requests)
            if request and request.get("id"):
                repo.update_access_request(
                    str(request["id"]),
                    request_status="downloaded",
                    downloaded_at=datetime.now().isoformat(timespec="minutes"),
                )
            repo.add_event(
                str(case_row.get("id") or ""),
                event_type="download_imported",
                event_source="import",
                title="Pacchetto PDP importato nel fascicolo",
                description=f"{len(created_local)} nuovi documenti locali, {linked_module} documenti classificati.",
                payload_json={
                    "created_local": len(created_local),
                    "linked_module": linked_module,
                    "import_status": import_status,
                },
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
        return {
            "created_local": created_local,
            "linked_module": linked_module,
            "import_status": import_status,
        }

    def _pdp_penale_build_checklist(
        fasc: Fascicolo,
        case_form: dict[str, Any],
        active_case: dict[str, Any],
        local_documents: list[dict[str, Any]],
        module_documents: list[dict[str, Any]],
        access_requests: list[dict[str, Any]],
        pec_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        nomina_docs = [
            doc for doc in (local_documents + module_documents)
            if str(doc.get("role_suggestion") or doc.get("document_role") or "") == "nomination"
        ]
        payment_docs = [
            doc for doc in (local_documents + module_documents)
            if str(doc.get("role_suggestion") or doc.get("document_role") or "") == "payment_receipt"
        ]
        legal_aid_docs = [
            doc for doc in (local_documents + module_documents)
            if str(doc.get("role_suggestion") or doc.get("document_role") or "") == "legal_aid_order"
        ]
        request = access_requests[0] if access_requests else {}
        password_received = bool(int(active_case.get("pec_password_received") or 0)) or any(
            str(msg.get("extracted_password") or "").strip() for msg in pec_messages
        )
        download_until = (
            str(request.get("download_available_until") or "").strip()
            or str(active_case.get("download_available_until") or "").strip()
        )
        ready_prereq = all(
            [
                str(case_form.get("office_name") or "").strip(),
                str(case_form.get("register_number") or "").strip(),
                _pdp_penale_int(case_form.get("register_year"), 0) > 0,
                str(case_form.get("assisted_party_name") or "").strip(),
                str(case_form.get("defense_counsel_name") or "").strip(),
                str(case_form.get("defense_counsel_cf") or "").strip(),
            ]
        )

        def _step(done: bool, warning: bool = False) -> str:
            if done:
                return "success"
            return "warning" if warning else "secondary"

        return [
            {
                "title": "Verifica prerequisiti",
                "variant": _step(ready_prereq, warning=bool(case_form.get("office_name") or case_form.get("register_number"))),
                "done": ready_prereq,
                "detail": "Difensore, codice fiscale, assistito, ufficio e riferimento procedimento.",
            },
            {
                "title": "Verifica titolo di accesso",
                "variant": _step(str(active_case.get("nomination_status") or "") in {"deposited", "accepted"}, warning=bool(nomina_docs)),
                "done": str(active_case.get("nomination_status") or "") in {"deposited", "accepted"},
                "detail": "Nomina presente o giÃ  depositata/accettata.",
            },
            {
                "title": "Verifica allegati obbligatori",
                "variant": _step(bool(nomina_docs), warning=bool(payment_docs or legal_aid_docs)),
                "done": bool(nomina_docs),
                "detail": f"Nomina: {len(nomina_docs)} Â· PagoPA: {len(payment_docs)} Â· Gratuito patrocinio: {len(legal_aid_docs)}",
            },
            {
                "title": "Generazione richiesta accesso atti",
                "variant": _step(bool(request), warning=str(active_case.get('access_status') or '') in {'ready', 'submitted'}),
                "done": bool(request),
                "detail": "Prepara la richiesta, registra il deposito e mantieni il riferimento interno.",
            },
            {
                "title": "Monitoraggio esito ministeriale",
                "variant": _step(
                    str(active_case.get("current_ministry_status") or "") in {"ACCETTATO", "IN_VERIFICA"},
                    warning=bool(active_case.get("current_ministry_status")),
                ),
                "done": str(active_case.get("current_ministry_status") or "") in {"ACCETTATO", "IN_VERIFICA"},
                "detail": f"Stato tecnico: {_pdp_penale_status_label(active_case.get('current_ministry_status'))}",
            },
            {
                "title": "PEC, password e finestra download",
                "variant": _step(password_received, warning=bool(download_until)),
                "done": password_received,
                "detail": f"Password PEC: {'ricevuta' if password_received else 'assente'}{f' Â· Disponibile fino al {download_until}' if download_until else ''}",
            },
            {
                "title": "Import fascicolo nel gestionale",
                "variant": _step(str(active_case.get("import_status") or "") == "completed", warning=str(active_case.get("import_status") or "") in {"waiting_download", "downloaded", "partial_import"}),
                "done": str(active_case.get("import_status") or "") == "completed",
                "detail": f"Stato import: {_pdp_penale_status_label(active_case.get('import_status'))}",
            },
        ]

    def _pdp_penale_build_workspace(fasc: Fascicolo, cliente: Optional[Cliente] = None) -> dict[str, Any]:
        repo = get_pdp_penale()
        gf = get_fascicoli()
        cases = repo.list_cases_for_practice(fasc.id)
        active_case_id = str(request.args.get("case_id") or "").strip()
        active_case = next((row for row in cases if str(row.get("id")) == active_case_id), None)
        if active_case is None and cases:
            active_case = cases[0]
        active_case = dict(active_case or {})
        case_form = _pdp_penale_case_defaults(fasc, cliente)
        if active_case:
            case_form.update({k: v for k, v in active_case.items() if v not in (None, "")})
        local_documents = _pdp_penale_local_documents(fasc, gf)
        module_documents = repo.list_case_documents(str(active_case.get("id") or "")) if active_case else []
        module_documents = _pdp_penale_module_documents_enriched(fasc, gf, module_documents)
        access_requests = repo.list_access_requests(str(active_case.get("id") or "")) if active_case else []
        pec_messages = repo.list_pec_messages(str(active_case.get("id") or "")) if active_case else []
        tasks = repo.list_tasks(str(active_case.get("id") or "")) if active_case else []
        open_tasks = [task for task in tasks if str(task.get("status") or "") in {"open", "in_progress"}]
        events = repo.list_case_events(str(active_case.get("id") or "")) if active_case else []
        primary_request = _pdp_penale_primary_access_request(access_requests) if access_requests else {}
        download_until = (
            str(primary_request.get("download_available_until") or "").strip()
            or str(active_case.get("download_available_until") or "").strip()
        )
        password_available = bool(int(active_case.get("pec_password_received") or 0)) or any(
            str(msg.get("extracted_password") or "").strip() for msg in pec_messages
        )
        checklist = _pdp_penale_build_checklist(
            fasc,
            case_form,
            active_case,
            local_documents,
            module_documents,
            access_requests,
            pec_messages,
        )
        return {
            "cases": cases,
            "active_case": active_case,
            "case_form": case_form,
            "events": events,
            "module_documents": module_documents,
            "local_documents": local_documents,
            "access_requests": access_requests,
            "primary_request": primary_request,
            "pec_messages": pec_messages,
            "tasks": tasks,
            "open_tasks": open_tasks,
            "wizard_checklist": checklist,
            "deposit_documents": _pdp_penale_build_deposit_documents(local_documents),
            "password_available": password_available,
            "download_available_until": download_until,
            "download_state": _pdp_penale_download_state(download_until),
            "stats": {
                "case_count": len(cases),
                "documents_count": len(module_documents),
                "requests_count": len(access_requests),
                "pec_count": len(pec_messages),
                "tasks_open": len(open_tasks),
            },
        }

    def _pdp_penale_summary_for_fascicolo(fasc: Fascicolo) -> dict[str, Any]:
        if fasc.tipo != TipoFascicolo.PENALE:
            return {}
        repo = get_pdp_penale()
        cases = repo.list_overview_for_practice(fasc.id)
        active = dict(cases[0]) if cases else {}
        return {
            "enabled": True,
            "url": url_for("pdp_penale_workspace", id_fasc=fasc.id),
            "case_count": len(cases),
            "active_case": active,
            "has_case": bool(active),
            "open_tasks": int(active.get("open_tasks_count") or 0) if active else 0,
            "documents_count": int(active.get("documents_count") or 0) if active else 0,
        }

    return {
        "pdp_penale_bool": _pdp_penale_bool,
        "pdp_penale_int": _pdp_penale_int,
        "pdp_penale_float": _pdp_penale_float,
        "pdp_penale_status_label": _pdp_penale_status_label,
        "require_pdp_penale_fascicolo": _require_pdp_penale_fascicolo,
        "require_pdp_penale_case": _require_pdp_penale_case,
        "pdp_penale_case_defaults": _pdp_penale_case_defaults,
        "pdp_penale_access_status_from_request_status": _pdp_penale_access_status_from_request_status,
        "pdp_penale_local_documents": _pdp_penale_local_documents,
        "pdp_penale_module_documents_enriched": _pdp_penale_module_documents_enriched,
        "pdp_penale_request_reference": _pdp_penale_request_reference,
        "pdp_penale_primary_access_request": _pdp_penale_primary_access_request,
        "pdp_penale_generate_request_pdf": _pdp_penale_generate_request_pdf,
        "pdp_penale_find_case_local_document": _pdp_penale_find_case_local_document,
        "pdp_penale_sync_case_mailbox": _pdp_penale_sync_case_mailbox,
        "pdp_penale_import_download_items": _pdp_penale_import_download_items,
        "pdp_penale_build_workspace": _pdp_penale_build_workspace,
        "pdp_penale_summary_for_fascicolo": _pdp_penale_summary_for_fascicolo,
        "ensure_pdp_penale_case_after_import": _ensure_pdp_penale_case_after_import,
    }
