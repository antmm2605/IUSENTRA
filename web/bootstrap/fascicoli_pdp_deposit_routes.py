"""Deposito PDP Penale routes."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, redirect, request, url_for

from legal_deposit.models import DepositDocument, PreflightStatus
from legal_deposit.penal_rules import (
    legacy_pdp_ministry_status,
    normalize_pdp_ministry_status,
    pdp_ministry_statuses,
)
from legal_deposit.policies import channel_profile_for
from legal_deposit.validators import DocumentPreflightValidator


def register_fascicoli_pdp_deposit_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_pdp_penale: Callable[[], Any],
    audit: Callable[..., None],
    sync_pubblica: Callable[..., None],
    require_pdp_penale_fascicolo: Callable[..., Any],
    require_pdp_penale_case: Callable[..., dict[str, Any]],
    pdp_penale_request_reference: Callable[..., str],
    pdp_penale_primary_access_request: Callable[..., dict[str, Any]],
    pdp_penale_find_case_local_document: Callable[..., Any],
    decrypt_doc: Callable[[bytes], bytes],
    resolve_ufficio_destinatario: Callable[..., dict[str, Any] | None],
    polis_demo_mode: Callable[[], bool],
) -> None:
    """Register PDP deposit endpoint with preflight and conscious confirmation."""

    @app.route("/fascicoli/<id_fasc>/penale/pdp/case/<case_id>/deposit", methods=["POST"])
    def pdp_penale_deposit_request(id_fasc: str, case_id: str):
        try:
            fascicolo = require_pdp_penale_fascicolo(id_fasc)
            repo = get_pdp_penale()
            case_row = require_pdp_penale_case(repo, case_id, fascicolo.id)
            if str(request.form.get("confirm_lawyer_review") or "").strip().lower() not in {
                "1",
                "on",
                "true",
                "si",
            }:
                raise ValueError(
                    "Prima della firma o dell'invio devi confermare di aver verificato "
                    "contenuto, allegati, ufficio, RG e canale PDP."
                )
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
                _run_pdp_preflight(
                    repo=repo,
                    case_id=case_id,
                    documento=documento,
                    tmp_path=tmp_path,
                    office_name=str(case_row.get("office_name") or ""),
                )
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

            _persist_pdp_deposit_result(
                repo=repo,
                case_id=case_id,
                case_row=case_row,
                esito=esito,
                request_reference=pdp_penale_request_reference,
                primary_access_request=pdp_penale_primary_access_request,
                user_id=getattr(g.utente_corrente, "id", ""),
            )
            codice_esito = str(esito.get("codiceEsito") or "").strip()
            stato_canonical = normalize_pdp_ministry_status(esito.get("stato") or "") or (
                "INVIATO" if codice_esito in {"0", "1"} else ""
            )
            audit(
                "fascicoli.pdp_penale.deposit",
                "fascicolo",
                id_fasc,
                dettagli=f"Deposito PDP case {case_id}: {stato_canonical or codice_esito}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            flash(
                "Deposito PDP registrato: "
                + str(esito.get("descrizioneEsito") or stato_canonical or "esito non disponibile"),
                "success" if _pdp_deposit_success(esito) else "warning",
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


def _run_pdp_preflight(
    *,
    repo: Any,
    case_id: str,
    documento: Any,
    tmp_path: str,
    office_name: str,
) -> None:
    signature_type = (
        "CADES_BES"
        if str(documento.nome or "").lower().endswith(".p7m")
        else ("PADES" if bool(getattr(documento, "firmato_digitalmente", False)) else "")
    )
    deposit_document = DepositDocument(
        document_id=str(documento.id),
        role="MAIN_ACT",
        filename=str(documento.nome or Path(tmp_path).name),
        path=tmp_path,
        mime_type="application/pkcs7-mime"
        if str(documento.nome or "").lower().endswith(".p7m")
        else "application/pdf",
        size_bytes=Path(tmp_path).stat().st_size,
        signed=bool(getattr(documento, "firmato_digitalmente", False)),
        signature_format=signature_type,
        pdfa=bool(getattr(documento, "pdfa", False)),
    )
    preflight_results = DocumentPreflightValidator().validate(
        documents=[deposit_document],
        profile=channel_profile_for("pdp_penale"),
        office_name=office_name,
    )
    error_results = [result for result in preflight_results if result.status == PreflightStatus.ERROR]
    if error_results:
        first_error = error_results[0]
        repo.add_event(
            case_id,
            event_type="deposit_preflight_failed",
            event_source="system",
            title="Precontrollo deposito PDP non superato",
            description=first_error.message,
            payload_json={
                "error_code": first_error.code,
                "checks": [result.to_dict() for result in preflight_results],
            },
            created_by_user_id=getattr(g.utente_corrente, "id", ""),
        )
        raise ValueError(
            "Precontrollo deposito non superato: "
            f"{first_error.message} {first_error.suggested_fix}".strip()
        )
    warning_results = [result for result in preflight_results if result.status == PreflightStatus.WARNING]
    if warning_results:
        repo.add_event(
            case_id,
            event_type="deposit_preflight_warning",
            event_source="system",
            title="Precontrollo deposito PDP con avvisi",
            description=f"{len(warning_results)} avvisi da verificare prima dell'invio.",
            payload_json={"checks": [result.to_dict() for result in warning_results]},
            created_by_user_id=getattr(g.utente_corrente, "id", ""),
        )
        for warning in warning_results[:3]:
            flash(f"Avviso predeposito: {warning.message}", "warning")


def _persist_pdp_deposit_result(
    *,
    repo: Any,
    case_id: str,
    case_row: dict[str, Any],
    esito: dict[str, Any],
    request_reference: Callable[..., str],
    primary_access_request: Callable[..., dict[str, Any]],
    user_id: str,
) -> None:
    codice_esito = str(esito.get("codiceEsito") or "").strip()
    stato_canonical = normalize_pdp_ministry_status(esito.get("stato") or "") or (
        "INVIATO" if codice_esito in {"0", "1"} else ""
    )
    stato = legacy_pdp_ministry_status(stato_canonical)
    success = _pdp_deposit_success(esito)
    existing_requests = repo.list_access_requests(case_id)
    request_row = primary_access_request(existing_requests)
    submitted_at = str(esito.get("dataDeposito") or datetime.now().isoformat(timespec="minutes"))
    if request_row and request_row.get("id"):
        repo.update_access_request(
            str(request_row["id"]),
            request_status="submitted" if success else "technical_error",
            request_reference=str(
                esito.get("idDeposito")
                or request_row.get("request_reference")
                or request_reference(case_row)
            ),
            submitted_at=submitted_at,
            ministry_status=stato or None,
            ministry_status_canonical=stato_canonical or None,
            notes=str(esito.get("descrizioneEsito") or "").strip() or None,
        )
    else:
        repo.create_access_request(
            case_id,
            request_type="access_to_case_file",
            request_reference=str(esito.get("idDeposito") or request_reference(case_row)),
            request_status="submitted" if success else "technical_error",
            submitted_at=submitted_at,
            ministry_status=stato or None,
            ministry_status_canonical=stato_canonical or None,
            notes=str(esito.get("descrizioneEsito") or "").strip() or None,
        )
    repo.update_case(
        case_id,
        access_status="submitted" if success else "technical_error",
        current_ministry_status=stato
        if stato in {"INVIATO", "IN_TRANSITO", "ACCETTATO", "IN_VERIFICA", "RIFIUTATO", "ERRORE_TECNICO"}
        else None,
        current_ministry_status_canonical=stato_canonical if stato_canonical in pdp_ministry_statuses() else None,
        notes=str(esito.get("descrizioneEsito") or case_row.get("notes") or "").strip() or None,
    )
    repo.add_event(
        case_id,
        event_type="deposit_submitted" if success else "deposit_failed",
        event_source="ministry" if success else "system",
        title="Deposito PDP inviato" if success else "Deposito PDP non riuscito",
        description=str(esito.get("descrizioneEsito") or "").strip(),
        payload_json=esito,
        created_by_user_id=user_id,
    )
    if success:
        _ensure_pdp_monitoring_tasks(repo, case_id=case_id, user_id=user_id)


def _ensure_pdp_monitoring_tasks(repo: Any, *, case_id: str, user_id: str) -> None:
    existing_tasks = repo.list_tasks(case_id, only_open=True)
    if not any(str(task.get("task_type") or "") == "check_pec" for task in existing_tasks):
        repo.create_task(
            case_id,
            task_type="check_pec",
            title="Controllare la PEC per password ed esiti PDP",
            description="Il deposito e stato inviato. Attendere PEC con esiti e password.",
            priority="high",
            status="open",
            assigned_user_id=user_id or None,
        )
    if not any(str(task.get("task_type") or "") == "wait_office_response" for task in existing_tasks):
        repo.create_task(
            case_id,
            task_type="wait_office_response",
            title="Monitorare autorizzazione ufficio PDP",
            description="Verificare stato inviato / in verifica / accolto / rigettato.",
            priority="medium",
            status="open",
            assigned_user_id=user_id or None,
        )


def _pdp_deposit_success(esito: dict[str, Any]) -> bool:
    codice_esito = str(esito.get("codiceEsito") or "").strip()
    stato = normalize_pdp_ministry_status(esito.get("stato") or "") or (
        "INVIATO" if codice_esito in {"0", "1"} else ""
    )
    return codice_esito in {"0", "1"} and stato != "ERRORE_TECNICO"

