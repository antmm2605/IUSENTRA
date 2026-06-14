"""Valutazione completa Regia Operativa e payload API/UI."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from legal_deposit.policies import AmbiguousChannelError, UnknownChannelError, channel_profile_for

from .deposit_readiness import run_predeposit_check
from .evidence_pack import generate_evidence_pack
from .messages import DEPOSIT_ACQUIRED, DEPOSIT_SENT_NOT_ACQUIRED, NO_REAL_TRANSPORT
from .models import DepositStatus, SlotStatus, ValidatorStatus
from .profiles import get_profile
from pct.pst_catalog import PST_BUSTA_ENCRYPTION_ALGORITHM
from .repository import PracticeEngineRepository
from .resolver import resolve_practice_profile
from .state_machine import derive_state


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text if text else default


def _euro(value: Any) -> str:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        number = 0.0
    text = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"EUR {text}"


def _tone(ok: bool, *, warning: bool = False) -> str:
    if ok:
        return "success"
    return "warning" if warning else "danger"


def _linked_preventivi(preventivi: list[Any], fascicolo: Any) -> list[Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    return [item for item in preventivi if _text(getattr(item, "id_fascicolo", "")) == fid]


def _linked_conferimenti(conferimenti: list[Any], fascicolo: Any, preventivi: list[Any]) -> list[Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    pids = {_text(getattr(item, "id", "")) for item in preventivi}
    return [
        item
        for item in conferimenti
        if _text(getattr(item, "id_fascicolo", "")) == fid or _text(getattr(item, "id_preventivo", "")) in pids
    ]


def _linked_parcelle(parcelle: list[Any], fascicolo: Any, preventivi: list[Any]) -> list[Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    pids = {_text(getattr(item, "id", "")) for item in preventivi}
    return [
        item
        for item in parcelle
        if _text(getattr(item, "id_fascicolo", "")) == fid or _text(getattr(item, "id_preventivo", "")) in pids
    ]


def _primary(rows: list[Any]) -> Any | None:
    return rows[0] if rows else None


def _query_url(path: str, **params: Any) -> str:
    cleaned = {key: _text(value) for key, value in params.items() if _text(value)}
    return f"{path}?{urlencode(cleaned)}" if cleaned else path


def _legal_deposit_profile_key(profile: Any) -> str:
    channel = _text(getattr(profile, "channel", "")).upper()
    registry = _text(getattr(profile, "registry", "")).upper()
    code = _text(getattr(profile, "code", "")).upper()
    procedure = _text(getattr(profile, "procedure_code", "")).upper()
    if channel in {"PCT_CIVILE", "PCT_LAVORO"}:
        if "SIECIC" in registry or "SIECIC" in code or "SIECIC" in procedure:
            return "pct_siecic"
        return "pct_sicid"
    if channel in {"PST_GDP", "SIGP_GDP"}:
        return "sigp_gdp"
    if channel == "PDP_PENALE":
        return "pdp_penale"
    if channel == "PAT_AMMINISTRATIVO":
        return "pat_siga"
    if channel == "PTT_TRIBUTARIO":
        return "ptt_sigit"
    if channel == "UNEP":
        return "unep"
    if channel in {"PEC_ONLY", "PEC", "STRAGIUDIZIALE_PEC"}:
        return "pec_stragiudiziale"
    return channel.lower()


def _deposit_delivery_policy(profile: Any | None) -> dict[str, Any]:
    if not profile or not getattr(profile, "depositable", False):
        return {
            "mode": "not_depositable",
            "label": "Procedura non depositabile",
            "detail": "La Regia non ha rilevato un canale di deposito telematico per questa pratica.",
            "officialChannel": "",
            "packageKind": "",
            "allowsDirectPec": False,
            "allowsPortalUpload": False,
            "requiresManualFinalUpload": False,
            "sendButtonLabel": "Invia deposito",
            "prepareButtonLabel": "Prepara sessione",
            "blockingRule": "Bloccano l'invio solo i requisiti obbligatori previsti dal canale e dalla normativa.",
            "nonBlockingRule": "Le mancanze non obbligatorie vengono segnalate come avvisi e non fermano l'invio.",
            "oneStepSigning": True,
            "immediateBatchSigning": True,
            "documentIndexGeneratedBySoftware": True,
        }
    try:
        channel_profile = channel_profile_for(_legal_deposit_profile_key(profile))
    except (AmbiguousChannelError, UnknownChannelError, ValueError) as exc:
        return {
            "mode": "manual_review",
            "label": "Canale da confermare",
            "detail": "Il profilo non basta per scegliere il canale ministeriale: conferma registro e rito prima del deposito.",
            "officialChannel": _text(getattr(profile, "channel", "")),
            "packageKind": "",
            "allowsDirectPec": False,
            "allowsPortalUpload": False,
            "requiresManualFinalUpload": True,
            "sendButtonLabel": "Conferma canale",
            "prepareButtonLabel": "Prepara controllo",
            "warning": str(exc),
            "blockingRule": "Bloccano l'invio solo i requisiti obbligatori previsti dal canale e dalla normativa.",
            "nonBlockingRule": "Le mancanze non obbligatorie vengono segnalate come avvisi e non fermano l'invio.",
            "oneStepSigning": True,
            "immediateBatchSigning": True,
            "documentIndexGeneratedBySoftware": True,
        }
    direct_pec = bool(channel_profile.allows_direct_pec)
    manual_upload = bool(channel_profile.requires_manual_final_upload or channel_profile.allows_portal_upload)
    requires_ministerial_transport = bool(direct_pec and channel_profile.package_kind == "pct_busta_enc")
    direct_pec_ready = bool(direct_pec and not requires_ministerial_transport)
    official_channel = channel_profile.name
    if _text(getattr(profile, "channel", "")).upper() == "PCT_LAVORO" and channel_profile.id == "pct_sicid":
        official_channel = "PCT lavoro / SICID"
    if direct_pec:
        mode = "direct_pec"
        if direct_pec_ready:
            label = "Invio PEC da software"
            detail = "La busta ministeriale viene preparata, cifrata e inviata alla PEC dell'ufficio."
            send_label = "Invia via PEC"
            prepare_label = "Prepara busta"
        else:
            label = "Invio PEC da completare"
            detail = (
                "Il canale PCT via PEC è corretto, ma manca il trasporto ministeriale reale: "
                f"Atto.msg deve essere cifrato in Atto.enc con algoritmo {PST_BUSTA_ENCRYPTION_ALGORITHM}. "
                "Il software prepara controlli e pacchetto; l'avvocato completa la busta conforme o collega "
                "l'adapter ministeriale, poi si riprende il presidio delle ricevute."
            )
            send_label = "Completa trasporto"
            prepare_label = "Prepara controllo busta"
    elif manual_upload:
        mode = "portal_upload"
        label = "Deposito su portale"
        detail = "Il software prepara pacchetto, controlli e ricevute attese; il deposito finale avviene nell'area riservata del portale ufficiale."
        send_label = "Apri portale"
        prepare_label = "Prepara pacchetto"
    else:
        mode = "manual_review"
        label = "Canale da presidiare"
        detail = "Il profilo richiede una verifica professionale prima della scelta del canale di deposito."
        send_label = "Conferma canale"
        prepare_label = "Prepara controllo"
    return {
        "mode": mode,
        "label": label,
        "detail": detail,
        "officialChannel": official_channel,
        "packageKind": channel_profile.package_kind,
        "xmlSchemaName": channel_profile.xml_schema_name,
        "allowsDirectPec": direct_pec,
        "directPecReady": direct_pec_ready,
        "allowsPortalUpload": bool(channel_profile.allows_portal_upload),
        "requiresManualFinalUpload": bool(channel_profile.requires_manual_final_upload),
        "requiresGuidedCompletion": bool(requires_ministerial_transport),
        "missingOperationalStep": (
            f"Atto.enc ministeriale cifrato {PST_BUSTA_ENCRYPTION_ALGORITHM}"
            if requires_ministerial_transport
            else ""
        ),
        "guidedNextActions": (
            [
                "Prepara e controlla atto principale, allegati, firme e DatiAtto.xml.",
                f"Genera o collega Atto.enc cifrato {PST_BUSTA_ENCRYPTION_ALGORITHM} con redattore o adapter ministeriale.",
                "Importa o presidia ricevuta di accettazione, RdAC ed esiti nel fascicolo.",
            ]
            if requires_ministerial_transport
            else []
        ),
        "requiresEncryption": bool(channel_profile.requires_encryption or channel_profile.package_kind == "pct_busta_enc"),
        "maxTotalSizeMb": channel_profile.max_total_size_mb,
        "maxSingleFileSizeMb": channel_profile.max_single_file_size_mb,
        "acceptedSignatureFormats": list(channel_profile.accepted_signature_formats),
        "receiptTypes": list(channel_profile.receipt_types),
        "sendButtonLabel": send_label,
        "prepareButtonLabel": prepare_label,
        "blockingRule": "Bloccano l'invio solo i requisiti obbligatori previsti dal canale e dalla normativa.",
        "nonBlockingRule": "Le mancanze non obbligatorie vengono segnalate come avvisi e non fermano l'invio.",
        "oneStepSigning": True,
        "immediateBatchSigning": True,
        "documentIndexGeneratedBySoftware": True,
        "note": channel_profile.defender_channel_note,
    }


def _channel_display_label(profile: Any, delivery_policy: dict[str, Any]) -> str:
    channel = _text(getattr(profile, "channel", "")).upper()
    registry = _text(getattr(profile, "registry", "")).upper()
    if channel == "PCT_LAVORO":
        return "PCT lavoro / SICID" if "SIECIC" not in registry else "PCT lavoro / SIECIC"
    if channel == "PCT_CIVILE":
        return "PCT civile / SIECIC" if "SIECIC" in registry else "PCT civile / SICID"
    if channel in {"PST_GDP", "SIGP_GDP"}:
        return "SIGP / Giudice di Pace"
    if channel == "PDP_PENALE":
        return "PDP penale"
    if channel == "PAT_AMMINISTRATIVO":
        return "PAT / SIGA"
    if channel == "PTT_TRIBUTARIO":
        return "PTT / SIGIT"
    if channel == "UNEP":
        return "UNEP"
    if channel in {"PEC_ONLY", "PEC", "STRAGIUDIZIALE_PEC"}:
        return "PEC"
    official = _text(delivery_policy.get("officialChannel"))
    return official or channel.replace("_", " ")


def ensure_profile_for_fascicolo(
    repository: PracticeEngineRepository,
    *,
    fascicolo: Any,
    preventivo: Any | None = None,
    conferimento: Any | None = None,
    actor: str = "",
    manual_code: str = "",
) -> tuple[Any, dict[str, Any]]:
    snapshot = repository.get_profile_snapshot(_text(getattr(fascicolo, "id", "")))
    if snapshot:
        profile = get_profile(snapshot.get("code") or snapshot.get("procedure_code") or snapshot.get("practice_id"))
        if profile:
            repository.ensure_slots(_text(getattr(fascicolo, "id", "")), profile)
            repository.ensure_checklist(_text(getattr(fascicolo, "id", "")), profile)
            return profile, {"profile": profile.to_dict(), "confidence": 1.0, "reason": "profilo gia' applicato", "alternatives": [], "needs_manual_confirmation": False}
    resolver = resolve_practice_profile(
        preventivo=preventivo,
        conferimento=conferimento,
        fascicolo=fascicolo,
        manual_code=manual_code,
    )
    if resolver.profile:
        repository.apply_profile(_text(getattr(fascicolo, "id", "")), resolver.profile, actor=actor, reason=resolver.reason)
    return resolver.profile, resolver.to_dict()


def _economic_summary(
    preventivo: Any | None,
    conferimento: Any | None,
    parcelle: list[Any],
    repository: PracticeEngineRepository,
    fascicolo_id: str,
    *,
    fascicolo: Any | None = None,
) -> dict[str, Any]:
    paid = [
        item
        for item in parcelle
        if _enum_value(getattr(item, "stato", "")).upper() in {"PAGATA", "SALDATA"} or _text(getattr(item, "data_pagamento", ""))
    ]
    paid_ids = {_text(getattr(item, "id", "")) for item in paid}
    primary_parcella = _primary(parcelle)
    unpaid_parcella = next((item for item in parcelle if _text(getattr(item, "id", "")) not in paid_ids), primary_parcella)
    preventivo_id = _text(getattr(preventivo, "id", ""))
    conferimento_id = _text(getattr(conferimento, "id", ""))
    parcella_id = _text(getattr(primary_parcella, "id", ""))
    payment_parcella_id = _text(getattr(unpaid_parcella, "id", ""))
    cliente_id = (
        _text(getattr(preventivo, "id_cliente", ""))
        or _text(getattr(conferimento, "id_cliente", ""))
        or _text(getattr(primary_parcella, "id_cliente", ""))
        or _text(getattr(fascicolo, "id_cliente", ""))
    )
    preventivo_href = f"/preventivi/p/{preventivo_id}" if preventivo_id else _query_url(
        "/preventivi/nuovo",
        id_fascicolo=fascicolo_id,
        id_cliente=cliente_id,
        from_page="fascicolo",
    )
    conferimento_href = f"/preventivi/conferimento/{conferimento_id}" if conferimento_id else _query_url(
        "/preventivi/conferimento/nuovo",
        id_preventivo=preventivo_id,
        id_fascicolo=fascicolo_id,
        id_cliente=cliente_id,
        from_page="fascicolo",
    )
    proforma_href = _query_url("/fatturazione", id_documento=parcella_id) if parcella_id else _query_url(
        "/fatturazione/nuova",
        id_fascicolo=fascicolo_id,
        id_cliente=cliente_id,
        id_preventivo=preventivo_id,
    )
    payment_href = _query_url(
        "/incassi-pagamenti",
        id_fascicolo=fascicolo_id,
        id_parcella=payment_parcella_id or parcella_id,
    ) if (payment_parcella_id or parcella_id) else proforma_href
    emitted = bool(parcelle)
    total = sum(float(getattr(item, "netto_a_pagare", 0.0) or getattr(item, "totale", 0.0) or 0.0) for item in parcelle)
    override = [event for event in repository.list_audit(fascicolo_id) if getattr(event, "event_type", "") == "ECONOMIC_OVERRIDE"]
    return {
        "preventivoAccepted": bool(preventivo and (_enum_value(getattr(preventivo, "stato", "")).upper() in {"ACCETTATO", "CONVERTITO"} or _text(getattr(preventivo, "accettato_il", "")))),
        "preventivoId": preventivo_id,
        "preventivoDate": _text(getattr(preventivo, "accettato_il", "")),
        "preventivoHref": preventivo_href,
        "conferimentoSigned": bool(conferimento and (getattr(conferimento, "firma_cliente_eseguita", False) or _text(getattr(conferimento, "firma_cliente_il", "")))),
        "conferimentoId": conferimento_id,
        "conferimentoDate": _text(getattr(conferimento, "firma_cliente_il", "")),
        "conferimentoHref": conferimento_href,
        "proformaIssued": emitted,
        "proformaHref": proforma_href,
        "primaryParcellaId": parcella_id,
        "paymentRegistered": bool(paid),
        "paymentHref": payment_href,
        "paymentParcellaId": payment_parcella_id,
        "invoiceIssued": emitted,
        "agreedFee": _euro(getattr(conferimento, "compenso_pattuito", 0.0) or getattr(preventivo, "totale", 0.0)),
        "expenses": _euro(getattr(preventivo, "totale_spese", 0.0) or getattr(preventivo, "anticipazioni_art15", 0.0)),
        "contributoUnificato": _euro(getattr(preventivo, "contributo_unificato", 0.0)),
        "totalDocuments": len(parcelle),
        "totalValue": _euro(total),
        "overrides": [
            {"id": event.id, "reason": event.reason, "message": event.message, "createdAt": event.created_at}
            for event in override
        ],
        "links": [
            {"label": "Preventivo", "href": preventivo_href},
            {"label": "Conferimento", "href": conferimento_href},
            {"label": "Parcella", "href": proforma_href},
            {"label": "Pagamento", "href": payment_href},
        ],
    }


def _checklist_payload(rows: list[Any], results: list[Any]) -> list[dict[str, Any]]:
    blocking_messages = {item.key: item for item in results if item.blocking}
    payload = []
    for item in rows:
        blocker = blocking_messages.get(item.key.lower()) or blocking_messages.get(item.key)
        status = "BLOCCATO" if blocker else ("COMPLETATO" if not item.required else "DA_COMPLETARE")
        payload.append(
            {
                "id": item.id,
                "key": item.key,
                "label": item.label,
                "required": item.required,
                "blocking": item.blocking,
                "status": status,
                "message": blocker.message if blocker else (item.message or "Controllo operativo da presidiare."),
                "suggestedAction": blocker.suggested_action if blocker else (item.suggested_action or "Completa il requisito quando applicabile."),
                "source": item.source,
            }
        )
    return payload


def _slots_payload(slots: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": slot.id,
            "slotKey": slot.slot_key,
            "label": slot.label,
            "type": slot.type,
            "required": slot.required,
            "blocking": slot.blocking,
            "documentId": slot.document_id,
            "status": slot.status,
            "validators": list(slot.validators),
            "lastValidationAt": slot.last_validation_at,
            "message": slot.message or ("Documento richiesto mancante." if slot.required and not slot.document_id else ""),
            "suggestedAction": slot.suggested_action or ("Carica o collega il documento richiesto." if slot.required and not slot.document_id else ""),
            "sortOrder": slot.sort_order,
            "linkAction": "",
            "validateAction": "",
        }
        for slot in slots
    ]


def _timeline_payload(events: list[Any], receipts: list[Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "id": event.id,
            "type": event.event_type,
            "status": event.status,
            "message": event.message,
            "createdAt": event.created_at,
            "evidenceRef": event.evidence_ref,
        }
        for event in events
    ]
    if not rows and receipts:
        rows.extend(
            {
                "id": receipt.id,
                "type": receipt.receipt_type,
                "status": receipt.status,
                "message": receipt.message,
                "createdAt": receipt.imported_at,
                "evidenceRef": receipt.id,
            }
            for receipt in receipts
        )
    return rows


def build_regia_payload(
    repository: PracticeEngineRepository,
    *,
    fascicolo: Any,
    cliente: Any | None = None,
    preventivi: list[Any] | None = None,
    conferimenti: list[Any] | None = None,
    parcelle: list[Any] | None = None,
    fascicoli_manager: Any | None = None,
    actor: str = "",
    manual_code: str = "",
) -> dict[str, Any]:
    fascicolo_id = _text(getattr(fascicolo, "id", ""))
    preventivi = _linked_preventivi(list(preventivi or []), fascicolo)
    conferimenti = _linked_conferimenti(list(conferimenti or []), fascicolo, preventivi)
    parcelle = _linked_parcelle(list(parcelle or []), fascicolo, preventivi)
    preventivo = _primary(preventivi)
    conferimento = _primary(conferimenti)
    profile, resolver_payload = ensure_profile_for_fascicolo(
        repository,
        fascicolo=fascicolo,
        preventivo=preventivo,
        conferimento=conferimento,
        actor=actor,
        manual_code=manual_code,
    )
    if not profile:
        return {
            "source": "repository reale",
            "mock_fallback": False,
            "page_state": "profilo_da_confermare",
            "profile": resolver_payload,
            "message": "Profilo pratica non determinato. Seleziona manualmente il profilo operativo.",
            "actions": {"applyProfile": f"/api/v1/ui/fascicoli/{fascicolo_id}/regia/applica-profilo"},
        }
    readiness = run_predeposit_check(
        repository,
        fascicolo=fascicolo,
        profile=profile,
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
        parcelle=parcelle,
        fascicoli_manager=fascicoli_manager,
    )
    slots = readiness["slots"]
    checklist = repository.list_checklist(fascicolo_id)
    sessions = repository.list_deposit_sessions(fascicolo_id)
    session = sessions[0] if sessions else None
    receipts = repository.list_receipts(session.id) if session else []
    timeline = repository.list_timeline(session.id) if session else []
    evidence = repository.get_evidence_pack(session.id) if session else None
    missing_slots = any(slot.required and slot.status in {SlotStatus.MANCANTE.value, SlotStatus.NON_VALIDO.value} for slot in slots)
    operational_state = session.status if session else derive_state(depositable=profile.depositable, validation_results=readiness["results"], slots_missing=missing_slots)
    blockers = [item for item in readiness["blockers"] if item.status != ValidatorStatus.NOT_APPLICABLE.value]
    warnings = list(readiness["warnings"])
    completion_den = max(1, len(checklist) + len([slot for slot in slots if slot.required]))
    completed = len([item for item in checklist if item.status == "COMPLETATO"]) + len([slot for slot in slots if slot.status in {SlotStatus.VALIDO.value, SlotStatus.NON_APPLICABILE.value}])
    completion = int(round(min(1.0, completed / completion_den) * 100))
    if blockers:
        next_action = blockers[0].suggested_action or blockers[0].message
    elif profile.depositable and not session:
        next_action = "Esegui il check di predeposito e prepara la sessione deposito."
    elif session and session.status == DepositStatus.ACQUISITO.value:
        next_action = DEPOSIT_ACQUIRED
    elif session and session.status in {DepositStatus.ACCETTATO_PEC.value, DepositStatus.CONSEGNATO.value, DepositStatus.CONTROLLI_OK.value}:
        next_action = DEPOSIT_SENT_NOT_ACQUIRED
    else:
        next_action = "Prosegui con la fase successiva della pratica."
    deposit_label = "Deposito telematico"
    if profile.channel in {"PEC_ONLY", "PEC"}:
        deposit_label = "Invia PEC / monitora risposta"
    elif not profile.depositable:
        deposit_label = "Procedura non depositabile"
    delivery_policy = _deposit_delivery_policy(profile)
    channel_label = _channel_display_label(profile, delivery_policy)
    return {
        "source": "repository reale",
        "mock_fallback": False,
        "page_state": "operativa",
        "generatedAt": readiness["results"][0].created_at if readiness["results"] else "",
        "header": {
            "title": _text(getattr(fascicolo, "titolo", "")),
            "practiceType": profile.name,
            "area": profile.area,
            "channel": channel_label,
            "channelCode": profile.channel,
            "registry": profile.registry,
            "workflow": profile.workflow_code,
            "operationalState": operational_state,
            "completion": completion,
            "nextAction": next_action,
        },
        "profile": {
            "code": profile.code,
            "name": profile.name,
            "practiceId": profile.practice_id,
            "procedureCode": profile.procedure_code,
            "confidence": resolver_payload.get("confidence", 1.0),
            "reason": resolver_payload.get("reason", ""),
            "needsManualConfirmation": resolver_payload.get("needs_manual_confirmation", False),
            "alternatives": resolver_payload.get("alternatives", []),
            "templateLabels": list(profile.template_labels),
            "deadlines": list(profile.deadlines),
            "depositable": profile.depositable,
        },
        "economics": _economic_summary(preventivo, conferimento, parcelle, repository, fascicolo_id, fascicolo=fascicolo),
        "checklist": _checklist_payload(checklist, readiness["results"]),
        "documentSlots": _slots_payload(slots),
        "validation": {
            "status": readiness["status"],
            "ready": readiness["ready"],
            "lastCheck": readiness["results"][0].created_at if readiness["results"] else "",
            "blockers": [item.__dict__ for item in blockers],
            "warnings": [item.__dict__ for item in warnings],
            "results": [item.__dict__ for item in readiness["results"]],
        },
        "deposit": {
            "label": deposit_label,
            "depositable": profile.depositable,
            "ready": readiness["ready"],
            "blocked": bool(blockers) or not profile.depositable,
            "blockReasons": [item.message for item in blockers] or ([] if profile.depositable else ["Questa procedura non prevede deposito telematico."]),
            "sessionId": session.id if session else "",
            "status": session.status if session else DepositStatus.NON_INVIATO.value,
            "transportMode": session.transport_mode if session else "non_configurato",
            "realTransport": bool(session.real_transport) if session else False,
            "message": (session.messages[0] if session and session.messages else (NO_REAL_TRANSPORT if profile.depositable else "Procedura non depositabile.")),
            "prepareAction": f"/api/v1/ui/fascicoli/{fascicolo_id}/depositi/prepara",
            "sendAction": f"/api/v1/ui/fascicoli/{fascicolo_id}/depositi/invia",
            "timelineAction": f"/api/v1/ui/fascicoli/{fascicolo_id}/depositi/{session.id}/timeline" if session else "",
            "importReceiptAction": f"/api/v1/ui/fascicoli/{fascicolo_id}/depositi/{session.id}/importa-ricevuta" if session else "",
            "deliveryPolicy": delivery_policy,
        },
        "timeline": _timeline_payload(timeline, receipts),
        "evidencePack": {
            "available": bool(evidence and evidence.available),
            "id": evidence.id if evidence else "",
            "href": f"/api/v1/ui/fascicoli/{fascicolo_id}/depositi/{session.id}/evidence-pack" if evidence and session else "",
            "hash": evidence.hash_sha256 if evidence else "",
        },
        "actions": {
            "applyProfile": f"/api/v1/ui/fascicoli/{fascicolo_id}/regia/applica-profilo",
            "recalculate": f"/api/v1/ui/fascicoli/{fascicolo_id}/regia/ricalcola",
            "predepositCheck": f"/api/v1/ui/fascicoli/{fascicolo_id}/predeposito/check",
        },
    }


def ensure_evidence_pack(repository: PracticeEngineRepository, *, fascicolo: Any, profile: Any, deposito_id: str):
    return generate_evidence_pack(repository, fascicolo=fascicolo, profile=profile, deposito_id=deposito_id)
